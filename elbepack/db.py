#!/usr/bin/env python
#
# ELBE - Debian Based Embedded Rootfilesystem Builder
# Copyright (C) 2013  Linutronix GmbH
#
# This file is part of ELBE.
#
# ELBE is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# ELBE is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with ELBE.  If not, see <http://www.gnu.org/licenses/>.

import os

from datetime import datetime
from shutil import (rmtree, copyfile)
from optparse import OptionParser

from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import (Column, Integer, String, Boolean, Sequence, DateTime)

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy.exc import OperationalError

from elbepack.elbeproject import ElbeProject
from elbepack.elbexml import (ElbeXML, ValidationError)

db_path     = '/var/cache/elbe'
db_location = 'sqlite:///' + db_path + '/elbe.db'

Base = declarative_base ()

class DbAction(object):

    actiondict = {}

    @classmethod
    def register(cls, action):
        cls.actiondict[action.tag] = action

    @classmethod
    def print_actions(cls):
        print 'available actions are:'
        for a in cls.actiondict:
            print '   ' + a

    def __new__(cls, node):
        action = cls.actiondict[node]
        return object.__new__(action, node)

    def __init__(self, node):
        self.node = node

def list_users ():
    session = get_db_session ()
    if not session:
        return None
    return session.query (User)

def list_projects ():
    session = get_db_session ()
    if not session:
        return None
    return session.query (Project)

def get_files (builddir):
    if not os.path.exists (builddir):
        print "project directory doesn't exist"
        return

    files = []
    try:
        with open (builddir+"/files-to-extract") as fte:
            files.append (fte.read ())
    except IOError as e:
        print e
        return None

    return files

# TODO think about return value and locking!
def build_project (builddir):
    if not os.path.exists (builddir):
        print "project directory doesn't exist"
        return

    session = get_db_session ()
    if not session:
        return

    p = None
    try:
        p = session.query (Project).filter(Project.builddir == builddir).one()
    except NoResultFound:
        print "project:", builddir, "isn't in db"
        return

    if p.status == "build_in_progress":
        print "project:", builddir, "invalid status:", p.status
        return

    if p.status == "empty_project":
        print "project:", builddir, "invalid status:", p.status
        return

    p.status = "build_in_progress"
    session.commit ()

    # TODO progress notifications
    ep = load_project (builddir)
    ep.build (skip_debootstrap = True)

    p.status = "build_done"
    session.commit ()

def set_xml (builddir, xml_file):

    if not os.path.exists (builddir):
        print "project directory doesn't exist"
        return

    session = get_db_session ()
    if not session:
        return

    p = None
    try:
        p = session.query (Project).filter(Project.builddir == builddir).one()
    except NoResultFound:
        print "project:", builddir, "isn't in db"
        return

    try:
        xml = ElbeXML (xml_file)
    except ValidationError as e:
        print e
        return

    p.name = xml.text ("project/name")
    p.version = xml.text ("project/version")
    p.edited = datetime.utcnow ()
    p.status = "needs_build"

    try:
        copyfile (xml_file, builddir+"/source.xml");
    except OSError as e:
        print "copy xml_file to builddir failed", e
        return

    try:
        session.commit ()
    except OperationalError as e:
        print e
        return

def del_project (builddir):

    session = get_db_session ()
    if not session:
        return

    p = None
    try:
        p = session.query (Project).filter(Project.builddir == builddir).one()
    except NoResultFound:
        print "project:", builddir, "isn't in db"
        return

    session.delete (p)

    if not os.path.exists (builddir):
        print "project directory doesn't exist"
        return

    try:
        rmtree (builddir)
    except OSError as e:
        print "remove build directory failed", e
        return

    try:
        session.commit ()
    except OperationalError as e:
        print e
        return

def create_project (builddir):
    if os.path.exists (builddir):
        print "project directory already exists"
        return

    try:
        os.makedirs (builddir)
    except OSError as e:
        print "create build directory failed", e
        return

    session = get_db_session ()
    if not session:
        return

    p = Project (builddir=builddir, status="empty_project")

    session.add (p)
    try:
        session.commit ()
    except OperationalError as e:
        print e
        return

def init_db (name, fullname, password, email, admin):
    if not os.path.exists (db_path):
        try:
            os.makedirs (db_path)
        except OSError as e:
            print e
            return

    session = get_db_session ()
    if not session:
        return

    u = User (name=name,
              fullname=fullname,
              password=password,
              email=email,
              admin=admin)

    session.add (u)
    try:
        session.commit ()
    except OperationalError as e:
        print e
        return

class InitAction(DbAction):
    tag = 'init'

    def __init__(self, node):
        DbAction.__init__(self, node)

    def execute(self, args):
        oparser = OptionParser (usage="usage: %prog db init [options]")
        oparser.add_option ("--name", dest="name", default="root")
        oparser.add_option ("--fullname", dest="fullname", default="Admin")
        oparser.add_option ("--password", dest="password", default="foo")
        oparser.add_option ("--email", dest="email", default="root@localhost")
        oparser.add_option ("--noadmin", dest="admin", default=True,
                action="store_false")

        (opt, arg) = oparser.parse_args (args)

        init_db (opt.name, opt.fullname, opt.password, opt.email, opt.admin)

DbAction.register(InitAction)

class ListProjectsAction(DbAction):

    tag = 'list_projects'

    def __init__(self, node):
        DbAction.__init__(self, node)

    def execute(self, args):
        projects = list_projects ()
        if not projects:
            return

        for p in projects:
            print p.builddir+":", p.name, "[", p.version, "]", p.edit

DbAction.register(ListProjectsAction)

class ListUsersAction(DbAction):

    tag = 'list_users'

    def __init__(self, node):
        DbAction.__init__(self, node)

    def execute(self, args):
        users = list_users ()
        if not users:
            return
        for u in users:
            print u.name+":", u.fullname, "<"+u.email+">"

DbAction.register(ListUsersAction)

class CreateProjectAction(DbAction):

    tag = 'create_project'

    def __init__(self, node):
        DbAction.__init__(self, node)

    def execute(self, args):
        if len (args) != 1:
            print "usage: elbe db create_project <project_dir>"
            return

        create_project (args[0])

DbAction.register(CreateProjectAction)

class DeleteProjectAction(DbAction):

    tag = 'del_project'

    def __init__(self, node):
        DbAction.__init__(self, node)

    def execute(self, args):
        if len (args) != 1:
            print "usage: elbe db del_project <project_dir>"
            return

        del_project (args[0])

DbAction.register(DeleteProjectAction)

class SetXmlAction(DbAction):

    tag = 'set_xml'

    def __init__(self, node):
        DbAction.__init__(self, node)

    def execute(self, args):
        if len (args) != 2:
            print "usage: elbe db set_xml <project_dir> <xml>"
            return

        set_xml (args[0], args[1])

DbAction.register(SetXmlAction)


class BuildAction(DbAction):

    tag = 'build'

    def __init__(self, node):
        DbAction.__init__(self, node)

    def execute(self, args):
        if len (args) != 1:
            print "usage: elbe db build <project_dir>"
            return

        build_project (args[0])

DbAction.register(BuildAction)


class GetFilesAction(DbAction):

    tag = 'get_files'

    def __init__(self, node):
        DbAction.__init__(self, node)

    def execute(self, args):
        if len (args) != 1:
            print "usage: elbe db get_files <project_dir>"
            return

        files = get_files (args[0])
        if not files:
            return
        for f in files:
            print f

DbAction.register(GetFilesAction)


def get_db_session ():
    engine = create_engine (db_location)
    try:
        Base.metadata.create_all (engine)
    except OperationalError:
        print 'cannot access db'
        return None

    Session = sessionmaker (bind=engine)
    return Session ()

class User(Base):
    __tablename__ = 'users'

    id = Column (Integer, Sequence('article_aid_seq', start=1001, increment=1),
                 primary_key=True)

    name     = Column (String)
    fullname = Column (String)
    password = Column (String)
    email    = Column (String)
    admin    = Column (Boolean)
    # projects = relationship("Project", backref="users")

    @classmethod
    def get_userid(self, user_name):
        user = DBSession.query(User).filter(User.name == user_name).first()
        return user.id

    @classmethod
    def verify_password(self, name, password):
        passwd = DBSession.query(User.password).\
                            filter(User.name == name).first()
        if passwd != None:
            return passwd[0] == password
        else:
            print "No user found "

    @classmethod
    def get_user_role(self, name):
        role = DBSession.query(User.password).filter(User.name == name).first()
        print role
        if role != None:
            return role[0] == True
        else:
            print "No role ? Wrong db entry ?"

    @classmethod
    def user_in_db(self, name):
        in_db = DBSession.query(User).filter(User.name == name).first()
        return in_db

class Project (Base):
    __tablename__ = 'projects'

    builddir = Column (String, primary_key=True)
    name     = Column (String)
    version  = Column (String)
    xml      = Column (String)
    status   = Column (String)
    edit     = Column (DateTime, default=datetime.utcnow)

def save_project (ep):
    session = get_db_session ()

    project = None

    try:
        project = session.query (Project).filter (
                    Project.builddir == ep.builddir).one ()
    except NoResultFound:
        pass

    with open (ep.builddir + "/source.xml") as xml_file:
        xml_str  = xml_file.read ()
        if not project:
            project = Project (name = ep.xml.text ("project/name"),
                               version = ep.xml.text ("project/version"),
                               builddir = ep.builddir,
                               xml = xml_str)
            session.add (project)
        else:
            project.edit = datetime.utcnow ()
            project.version = ep.xml.text ("project/version")
            project.xml = xml_str

    session.commit ()

def load_project (builddir):
    session = get_db_session ()
    try:
        p = session.query(Project).filter(Project.builddir == builddir).one()
        return ElbeProject (p.builddir, name=p.name)
    except NoResultFound:
        return None
