#!/bin/sh
# ADMIN APPROVAL REQUIRED; fresh isolated installation only, no service changes.
set -eu
PATH=/usr/sbin:/usr/bin:/sbin:/bin
export PATH
unset LD_PRELOAD LD_LIBRARY_PATH PYTHONPATH PYTHONHOME NODE_OPTIONS
test "$(id -u)" -eq 0
test "$#" -eq 5
repo=$1
node=$2
bwrap=$3
node_hash=$4
bwrap_hash=$5
dest=/opt/stacksense/diagram-artifacts
/usr/bin/python3.14 -I - "$dest" <<'PY'
import stat,sys
from pathlib import Path
target=Path(sys.argv[1])
for path in (target,*target.parents):
    if not path.exists() and not path.is_symlink(): continue
    info=path.lstat()
    if stat.S_ISLNK(info.st_mode) or info.st_uid!=0 or info.st_mode&0o022:
        raise SystemExit('untrusted existing installation ancestor')
PY
test ! -e "$dest"
test "$(findmnt -no FSTYPE -T /var/lib/stacksense/diagrams)" = ext4 || test "$(findmnt -no FSTYPE -T /var/lib/stacksense/diagrams)" = xfs
test -z "$(find /var/lib/stacksense/diagrams -mindepth 1 -maxdepth 1 ! -name lost+found -print -quit)"
if test -d /var/lib/stacksense/diagrams/lost+found; then
  test -z "$(find /var/lib/stacksense/diagrams/lost+found -mindepth 1 -maxdepth 1 -print -quit)"
fi
umask 022
install -d -o root -g root -m 0755 "$dest" "$dest/python"
/usr/bin/python3.14 -I -m venv "$dest/venv"
"$dest/venv/bin/python" -I -m pip install --no-input --requirement "$repo/requirements.txt"
# Copy code and proof fixtures, never .env, credentials, .git or node_modules.
test -z "$(find "$repo/backend" "$repo/tests" -name node_modules -prune -o -type l -print -quit)"
tar -C "$repo" --exclude=__pycache__ --exclude='*.pyc' --exclude=.git \
  --exclude='.env*' --exclude=node_modules -cf - backend tests | \
  tar -C "$dest/python" --no-same-owner --no-same-permissions -xf -
install -o root -g root -m 0444 "$repo/pytest.ini" "$repo/pyproject.toml" "$dest/python/"
sh "$repo/backend/platform/diagrams/deployment/install_diagram_runtime.sh" \
  "$repo" "$node" "$bwrap" "$node_hash" "$bwrap_hash"
# This marker admits ONLY the fixed hostile probe under the same sandbox.
printf 'B1-ISOLATED-PROOFS\n' > "$dest/deployment/proof-enabled"
chown root:root "$dest/deployment/proof-enabled"
chmod 0444 "$dest/deployment/proof-enabled"
"$dest/venv/bin/python" -I - "$dest/deployment/seal-fault-cases.json" <<'PY'
import json,os,sys
from uuid import uuid4
names=['before_copy','after_manifest.json','after_layout.json','after_members.json',
       'after_spec.json','after_scene.svg','after_verify','after_fsync','after_placement']
payload={'version':'1.0.0','cases':[{'checkpoint':name,'generation_id':str(uuid4())} for name in names]}
fd=os.open(sys.argv[1],os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o444)
with os.fdopen(fd,'w') as stream:
    json.dump(payload,stream,sort_keys=True);stream.flush();os.fsync(stream.fileno())
PY
echo 'Proof package staged only. Configure isolated PostgreSQL roles/configs and review transient proof commands; production dispatch remains untouched.'
