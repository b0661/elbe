## ELBE - Debian Based Embedded Rootfilesystem Builder
## Copyright (C) 2013  Linutronix GmbH
##
## This file is part of ELBE.
##
## ELBE is free software: you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published by
## the Free Software Foundation, either version 3 of the License, or
## (at your option) any later version.
##
## ELBE is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
## GNU General Public License for more details.
##
## You should have received a copy of the GNU General Public License
## along with ELBE.  If not, see <http://www.gnu.org/licenses/>.
##
#! /bin/sh

# This script is called by the debian-installer by preseed/late_command on install-initial-core-image.
# The script is called again as an init script on any following boot (first time on install-initial-image).
#

<%text>### BEGIN INIT INFO</%text>
# Provides:          init-elbe
# Required-Start:    $remote_fs $syslog $named
# Required-Stop:     $remote_fs $syslog $named
# Default-Start:     2 3 4 5
# Default-Stop:      0 1 6
# Short-Description: Run second stage elbe initialisation at boot time
# Description:       On first invocation install the elbe build environment.
#   On all other invocations do nothing.
<%text>### END INIT INFO</%text>

SCRIPT=elbe
RUNAS=root
NAME=elbe-init
SCRIPTNAME=/etc/init.d/$NAME
PIDFILE=/var/run/$NAME.pid
LOGFILE=/var/cache/elbe/$NAME.log

SCRIPT="echo 'elbe-init'" # Dummy by intention

ELBE_REPO_DIR=/media/elbe-repo

if [ -d "/target" ]; then
  # /target does exist, we assume the script is called from the debian-installer.
  # see Makefile.mako .stamps/stamp-install-initial-core-image

  # stop confusion /target is buildenv in this context
  ln -s /target /buildenv

  # Create a place for elbe
  mkdir -p /buildenv/var/cache/elbe/
  
  echo "--- Elbe init - 1st stage ---" >/buildenv$LOGFILE
  
  # Copy this script to make it an init script to be used on next boot
  cp /init-elbe.sh /buildenv$SCRIPTNAME >>/buildenv$LOGFILE 2>&1
  chmod 755 /buildenv$SCRIPTNAME >>/buildenv$LOGFILE 2>&1
  
  # Activate the init script
  in-target update-rc.d $NAME defaults
  
  # Prepare to share elbe repository.
  ELBE_INIT_REPO_DIR=/buildenv$ELBE_REPO_DIR
  mkdir -p $ELBE_INIT_REPO_DIR >>/buildenv$LOGFILE 2>&1
  # prepare for future mounting
  echo -e "elbe-repo\t$ELBE_REPO_DIR\t9p\ttrans=virtio,version=9p2000.L,rw\t0\t0" >>/target/etc/fstab 2>>/buildenv$LOGFILE

  # Prepare later mount of shared directories
% if prj.has("share-list"):
%    for share in prj.node("share-list"):
  mkdir -p /buildenv/media/${share.text("id")} >>/buildenv$LOGFILE 2>&1
  echo -e "${share.text("id")}\t/media/${share.text("id")}\t9p\ttrans=virtio,version=9p2000.L,rw\t0\t0" >>/target/etc/fstab 2>>/buildenv$LOGFILE
%    endfor
% endif

  # Remember source.xml
  cp source.xml /buildenv/var/cache/elbe/ >>/buildenv$LOGFILE 2>&1
  cp /etc/apt/apt.conf /buildenv/etc/apt/ >>/buildenv$LOGFILE 2>&1

  exit 0
fi

# /target does not exist, we assume the script is called as an init script on (re)boot.

if [ ! -f "/usr/bin/elbe" ]; then
  # elbe is not installed, we assume the script is called the first time from initd or systemd or upstart.
  # see Makefile.mako .stamps/stamp-install-initial-image
  
  echo "--- Elbe init - 2nd stage ---" >>$LOGFILE

  # -----------------
  # Clone any directories to be cloned.
  # Note: Cloning is done very early to allow other actions to access the clone(s).
  #       Needs rsync
  # -----------------

  # Assure rsync is available
  # Note: Make this an unattended install (always answer yes). 
  yes "Yes" | aptitude install -q -y -o Dpkg::Options::="--force-confdef" -o Dpkg::Options::="--force-confold" \
  rsync  2>>$LOGFILE
  
% if prj.has("clone-list"):
%    for clone in prj.node("clone-list"):
  # --- CLONE: ${clone.text("host-path")} to ${clone.text("initvm-path")} 
  # Mount directory to be cloned
  mkdir -p /media/${clone.text("id")} >>$LOGFILE 2>&1
  mount -t 9p -o trans=virtio,version=9p2000.L ${clone.text("id")} /media/${clone.text("id")} >>$LOGFILE 2>&1
  # Clone directory
  rsync --archive --inplace --hard-links \
%        for node in clone:
%            if node.tag == "include":
  --include="${node.text(".")}"\
%            endif
%            if node.tag == "exclude":
  --exclude="${node.text(".")}"\
%            endif
%        endfor
  /media/${clone.text("id")}/ ${clone.text("initvm-path")} >>$LOGFILE 2>&1
  # Make root the owner of the clone directory
  chgrp -R root ${clone.text("initvm-path")} >>$LOGFILE 2>&1
  chown -R root ${clone.text("initvm-path")} >>$LOGFILE 2>&1
  # Unmount shared directory of host
  umount /media/${clone.text("id")} >>$LOGFILE 2>&1
  rmdir -p /media/${clone.text("id")} >>$LOGFILE 2>&1
%    endfor
% endif

  # -----------------
  # Enable shared repo for elbe project
  # -----------------
  
  # Make root the owner of the project repository (Elbe share security is mapped -> no effect on host).
  chgrp -R root $ELBE_REPO_DIR >>$LOGFILE 2>&1
  chown -R root $ELBE_REPO_DIR >>$LOGFILE 2>&1
  
  # Prepend repo to apt sources.list to give it the highest priority.
  TMP_SOURCES_LIST=/tmp/sources.list
  echo "${apt_sources_list}" >$TMP_SOURCES_LIST
  cat /etc/apt/sources.list >>$TMP_SOURCES_LIST 2>>$LOGFILE
  cp $TMP_SOURCES_LIST /etc/apt/sources.list >>$LOGFILE 2>&1
  
  # Prepare for unattended update/install
  export DEBIAN_FRONTEND=noninteractive DEBIAN_PRIORITY=critical
  
  # Make all known to aptitude
  aptitude update -q >>$LOGFILE 2>&1
  
  # Try to solve any package conflicts and do a full upgrade
  yes "Yes" | aptitude full-upgrade -q -y -o Dpkg::Options::="--force-confdef" -o Dpkg::Options::="--force-confold" \
  2>>$LOGFILE
  
  # -----------------
  # Install any additional packages (including the elbe build environment)
  # Note: Must be done after the project repo is enabled.
  #       Make this an unattended install (always answer yes). 
  # -----------------

  yes "Yes" | aptitude install -q -y -o Dpkg::Options::="--force-confdef" -o Dpkg::Options::="--force-confold" \
  elbe-buildenv elbe-daemon elbe-soap openssh-client qemu-elbe-user-static rsync \
% for n in pkgs:
% if n.tag == "pkg":
    ${n.text(".")} \
% endif
% endfor
  2>>$LOGFILE

  
% if xml.has('target'):
  echo -n "running elbe buildchroot .. /var/cache/elbe/source.xml ..." >>$LOGFILE
  elbe buildchroot \
%  if opt.skip_validation:
  --skip-validation \
%  endif
%  if opt.skip_cds:
  --skip-cdrom \
%  endif
%  if opt.buildsources:
  --build-sources \
%  endif
%  if opt.buildtype:
  --buildtype=${buildtype} \
%  endif
  -t /var/cache/elbe/build \
  -o /var/cache/elbe/elbe-report.log \
  /var/cache/elbe/source.xml \
  >>$LOGFILE 2>&1
  echo "done" >>$LOGFILE
% endif

  if [ -f "/usr/bin/elbe" ]; then
    cp $LOGFILE $ELBE_SHARE_DIR/$NAME.log
    cp /var/cache/elbe/elbe-report.log $ELBE_SHARE_DIR/elbe-report.log
    sync
    shutdown -h now >>$LOGFILE 2>&1
    
    exit 0
  fi 
fi

# The 'real' init script

start() {
  if [ -f $PIDFILE ] && kill -0 $(cat $PIDFILE); then
    echo 'Service already running' >&2
    return 1
  fi
  echo "Starting service $NAME" >&2
  local CMD="$SCRIPT &>>\"$LOGFILE\" & echo \$!"
  su -c "$CMD" $RUNAS >"$PIDFILE"
  echo 'Service started' >&2
}

stop() {
  if [ ! -f "$PIDFILE" ] || ! kill -0 $(cat "$PIDFILE"); then
    echo 'Service not running' >&2
    return 1
  fi
  echo "Stopping service $NAME" >&2
  kill -15 $(cat "$PIDFILE") && rm -f "$PIDFILE"
  echo 'Service stopped' >&2
}

uninstall() {
  echo -n "Are you really sure you want to uninstall this service? That cannot be undone. [yes|No] "
  local SURE
  read SURE
  if [ "$SURE" = "yes" ]; then
    stop
    rm -f "$PIDFILE"
    echo "Notice: log file was not removed: '$LOGFILE'" >&2
    update-rc.d -f $NAME remove
    rm -fv "$0"
  fi
}

status() {
    printf "%-50s" "Checking $NAME..." >&2
    if [ -f $PIDFILE ]; then
        PID=$(cat $PIDFILE)
            if [ -z "$(ps axf | grep $PID | grep -v grep)" ]; then
                printf "%s\n" "The process appears to be dead but pidfile still exists" >&2
            else
                echo "Running, the PID is $PID" >&2
            fi
    else
        printf "%s\n" "Service not running" >&2
    fi
}


case "$1" in
  start)
    start
    ;;
  stop)
    stop
    ;;
  status)
    status
    ;;
  uninstall)
    uninstall
    ;;
  restart)
    stop
    start
    ;;
  *)
    echo "Usage: $0 {start|stop|status|restart|uninstall}"
esac

