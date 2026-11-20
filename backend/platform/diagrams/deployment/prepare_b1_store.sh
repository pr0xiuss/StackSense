#!/bin/sh
# ADMIN APPROVAL REQUIRED. Creates a NEW, isolated 4 GiB proof image only.
# Never formats a device or an existing image; no application data is removed.
set -eu
PATH=/usr/sbin:/usr/bin:/sbin:/bin
export PATH
unset LD_PRELOAD LD_LIBRARY_PATH PYTHONPATH PYTHONHOME
test "$(id -u)" -eq 0
test "$#" -eq 1 && test "$1" = --approved-new-4gib-proof-store
parent=/var/lib/stacksense
image=/var/lib/stacksense/diagram-b1-proof.ext4
store=/var/lib/stacksense/diagrams
/usr/bin/python3.14 -I - "$store" <<'PY'
import stat,sys
from pathlib import Path
target=Path(sys.argv[1])
for path in (target,*target.parents):
    if not path.exists() and not path.is_symlink(): continue
    info=path.lstat()
    if stat.S_ISLNK(info.st_mode) or info.st_uid!=0 or info.st_mode&0o022:
        raise SystemExit('untrusted existing store ancestor')
PY
test ! -e "$image"
! mountpoint -q "$store"
if test -e "$store"; then
  test -d "$store" && test ! -L "$store"
  test -z "$(find "$store" -mindepth 1 -maxdepth 1 -print -quit)"
fi
if test ! -d "$parent"; then install -d -o root -g root -m 0755 "$parent"; fi
install -d -o root -g root -m 0755 "$store"
/usr/bin/python3.14 -I - "$parent" "$image" <<'PY'
import os,stat,sys
from pathlib import Path
parent,image=map(Path,sys.argv[1:])
for path in (parent,*parent.parents):
    info=path.lstat()
    if stat.S_ISLNK(info.st_mode) or info.st_uid!=0 or info.st_mode&0o022:
        raise SystemExit('untrusted image parent')
fd=os.open(image,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
try:
    os.ftruncate(fd,4*1024**3)
    os.fsync(fd)
finally: os.close(fd)
PY
# The exact root-only image was just created exclusively above. A failure
# leaves it retained for administrator inspection, never automatically deleted.
fallocate -l 4G "$image"
/usr/sbin/mkfs.ext4 -q -F -m 0 "$image"
mount -o loop,nodev,nosuid,noexec "$image" "$store"
test "$(findmnt -no FSTYPE -T "$store")" = ext4
echo 'Disposable proof store mounted; no fstab or production service changed.'
