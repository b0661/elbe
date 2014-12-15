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
IMGSIZE?=20G
MEMSIZE?=1024
SMP?=`nproc`
INTERPRETER?=kvm
MACHINE?=pc
NICMODEL?=virtio
CONSOLE?=ttyS0,115200n1
LOOP_OFFSET?=1048576
HD_TYPE?=virtio
HD_NAME?=vda1
CDROM_TYPE?=scsi
GUIPORT?=${opt.guiport}
REPO_DIR?=.elbe-repo

<%
import os
import string

nicmac = prj.text('buildimage/NIC/MAC', default=defs, key='nicmac')
target_num = 1
%>

# Do not use graphic output but use console.
# Better suited than -nographic as we can easily add serial devices without some interference.
CLI_NOGRAPHIC=-curses -serial mon:stdio

# Basic qemu options
CLI_BASE=-no-reboot
CLI_BASE_INSTALL_INITIAL_CORE_IMAGE=-no-reboot -kernel .elbe-in/vmlinuz -initrd .elbe-gen/initrd-preseeded.gz -append 'root=/dev/$(HD_NAME) debconf_priority=critical console=$(CONSOLE) DEBIAN_FRONTEND=newt'

# The machine qemu shall virtualize
CLI_MACHINE=-M $(MACHINE) -m $(MEMSIZE) -smp $(SMP) -usb

# Drive images
CLI_HDD=-drive file=buildenv.img,if=$(HD_TYPE),bus=1,unit=0 \
% if prj.has("mirror/cdrom"):
 -drive file=${prj.text("mirror/cdrom")},if=$(CDROM_TYPE),media=cdrom,bus=1,unit=1 \
% endif

# Networking
CLI_NETWORK=-net nic,vlan=1,model=$(NICMODEL),macaddr='${nicmac}' -net user,vlan=1 \
 -redir tcp:$(GUIPORT)::8080 \
% if prj.has("buildimage/portforwarding"):
% for f in prj.node("buildimage/portforwarding"):
 -redir ${f.text("proto")}:${f.text("host")}::${f.text("buildenv")} \
% endfor
% endif

# Shared Directories (incl. elbe repository directory)
CLI_SHARED_DIR=-fsdev local,security_model=mapped,id=fsdev0,path=$(REPO_DIR) \
 -device virtio-9p-pci,id=fs0,fsdev=fsdev0,mount_tag=elbe-repo \
% if prj.has("share-list"):
<%   share_nr = 0 %>\
%    for share in prj.node("share-list"):
<%
         share_nr += 1 
         share_host_path = os.path.abspath(share.text("host-path")) 
%>\
 -fsdev local,security_model=mapped,id=fsdev${share_nr},path=${share_host_path} \
 -device virtio-9p-pci,id=fs${share_nr},fsdev=fsdev${share_nr},mount_tag=${share.text("id")} \
%    endfor
% endif

# Additional serial device on host pty
CLI_SERIAL=-serial pty,id=elbe-serial-pty
#CLI_SERIAL=


all: .stamps/stamp-install-initial-image .elbe-gen/files-to-extract

.elbe-gen/initrd-preseeded.gz: .elbe-in/*
	rm -rf tmp-tree
	mkdir tmp-tree
	cp .elbe-in/*.cfg tmp-tree/
	-cp .elbe-in/apt.conf tmp-tree/
	mkdir -p tmp-tree/etc/apt
	-cp .elbe-in/apt.conf tmp-tree/etc/apt
	mkdir -p tmp-tree/usr/lib/post-base-installer.d
	cp .elbe-in/init-elbe.sh tmp-tree/
	cp .elbe-in/source.xml tmp-tree/
	mkdir -p .elbe-gen
	gzip -cd .elbe-in/initrd.gz >.elbe-gen/initrd-preseeded
	cd tmp-tree && find . | cpio -H newc -o --append -F ../.elbe-gen/initrd-preseeded
	gzip -9f .elbe-gen/initrd-preseeded
	rm -rf tmp-tree

.stamps/stamp-create-buildenv-img buildenv.img: .elbe-gen/initrd-preseeded.gz
	qemu-img create -f raw buildenv.img $(IMGSIZE)
	mkdir -p .stamps
	touch .stamps/stamp-create-buildenv-img

# Install the core debian in virtual machine (1st stage install)
#   We need a 2 stage install because shared directories can not be activated within the debian installer (1st stage).
#   See Makefile.mako for the whole 2 stage installation process.
.stamps/stamp-install-initial-core-image: .stamps/stamp-create-buildenv-img
	$(INTERPRETER) $(CLI_BASE_INSTALL_INITIAL_CORE_IMAGE) $(CLI_NOGRAPHIC) $(CLI_MACHINE) $(CLI_DEFAULTS) \
        $(CLI_SHARED_DIR) $(CLI_HDD) $(CLI_NETWORK) && reset
	mkdir -p .stamps
	touch .stamps/stamp-install-initial-core-image

# Install the elbe buildenv on top of debian in virtual machine (2nd stage install)
#   See Makefile.mako for the whole 2 stage installation process.
.stamps/stamp-install-initial-image: .stamps/stamp-install-initial-core-image
	mkdir -p .elbe-share
	$(INTERPRETER) $(CLI_BASE) $(CLI_NOGRAPHIC) $(CLI_MACHINE) $(CLI_DEFAULTS) \
        $(CLI_SHARED_DIR) $(CLI_HDD) $(CLI_NETWORK) && reset

run:
	$(INTERPRETER) $(CLI_BASE) $(CLI_MACHINE) $(CLI_DEFAULTS) \
        $(CLI_SHARED_DIR) $(CLI_HDD) $(CLI_NETWORK) && reset

run-con:
	$(INTERPRETER) $(CLI_BASE) $(CLI_NOGRAPHIC) $(CLI_MACHINE) $(CLI_DEFAULTS) \
        $(CLI_SHARED_DIR) $(CLI_HDD) $(CLI_NETWORK) && reset

run-con-serial:
	$(INTERPRETER) $(CLI_BASE) $(CLI_NOGRAPHIC) $(CLI_MACHINE) $(CLI_DEFAULTS) \
        $(CLI_SHARED_DIR) $(CLI_HDD) $(CLI_SERIAL) $(CLI_NETWORK) && reset

run-serial:
	$(INTERPRETER) $(CLI_BASE) $(CLI_MACHINE) $(CLI_DEFAULTS) \
        $(CLI_SHARED_DIR) $(CLI_HDD) $(CLI_SERIAL) $(CLI_NETWORK) -usb && reset

.elbe-gen/files-to-extract: .stamps/stamp-install-initial-image
	mkdir -p .elbe-gen
% if xml.has("project"):
	e2cp buildenv.img?offset=$(LOOP_OFFSET):/var/cache/elbe/build/files-to-extract .elbe-gen/
	for f in `cat .elbe-gen/files-to-extract`; do e2cp buildenv.img?offset=$(LOOP_OFFSET):/var/cache/elbe/build/$$f . ; done
	cat validation.txt
% endif

# Make an image for virtualbox
buildenv.vdi: .stamps/stamp-install-initial-core-image buildenv.img 
	qemu-img convert -O vdi buildenv.img buildenv.vdi

# Make an image for VMWare
buildenv.vmdk: .stamps/stamp-install-initial-core-image buildenv.img 
	qemu-img convert -O vmdk buildenv.img buildenv.vmdk

clean:
	rm -fr .stamps/stamp* buildenv.* .elbe-vm .elbe-gen

distclean: clean
	echo clean
