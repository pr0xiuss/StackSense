#!/bin/sh
# Administrator only. Reviewed sources and a preinstalled project dependency venv
# are prerequisites. Does not enable dispatch, install migrations, or start units.
set -eu
unset LD_PRELOAD LD_LIBRARY_PATH PYTHONPATH PYTHONHOME NODE_OPTIONS
test "$(id -u)" -eq 0 || { echo 'Administrator provisioning required' >&2; exit 78; }
test "$#" -eq 5 || { echo 'Usage: installer REPOSITORY VERIFIED_NODE VERIFIED_BWRAP NODE_SHA256 BWRAP_SHA256' >&2; exit 78; }
repo=$(realpath "$1")
node=$(realpath "$2")
bwrap=$(realpath "$3")
node_hash=$4
bwrap_hash=$5
test "${#node_hash}" -eq 64 && test "${#bwrap_hash}" -eq 64
test "$(sha256sum "$node" | cut -d' ' -f1)" = "$node_hash"
test "$(sha256sum "$bwrap" | cut -d' ' -f1)" = "$bwrap_hash"
dest=/opt/stacksense/diagram-artifacts
source_dir=$repo/backend/platform/diagrams
test -x "$dest/venv/bin/python" || { echo 'Provision root-owned Python 3.14 venv with declared project dependencies first' >&2; exit 78; }
test "$(stat -c %u "$dest/venv/bin/python")" -eq 0
# Fail before creating accounts/installing files when basic prerequisites fail.
test "$(findmnt -no FSTYPE -T /var/lib/stacksense/diagrams)" = ext4 || test "$(findmnt -no FSTYPE -T /var/lib/stacksense/diagrams)" = xfs || { echo 'Mount approved ext4/XFS store before provisioning' >&2; exit 78; }
test "$("$node" --version)" = v24.22.3
test "$("$bwrap" --version)" = 'bubblewrap 0.12.0'
test ! -u "$bwrap"
command -v getcap >/dev/null
test -z "$(getcap "$bwrap")"
test ! -e "$dest/deployment/runtime-lock.json" || { echo 'Existing deployment requires explicit upgrade review' >&2; exit 78; }
visudo -cf "$source_dir/deployment/diagram-artifacts.sudoers"
for tool in setfacl getfacl findmnt install ldd; do command -v "$tool" >/dev/null; done
"$dest/venv/bin/python" -I - "$dest" <<'PY'
import os,stat,sys
from pathlib import Path
root=Path(sys.argv[1])
for path in (root,*root.parents,*root.joinpath('venv').rglob('*')):
    if path.is_symlink():
        path=path.resolve(strict=True)
    info=path.stat()
    if info.st_uid!=0 or info.st_mode&0o022:
        raise SystemExit('Unprotected runtime/venv path')
if sys.version_info[:2]!=(3,14): raise SystemExit('Python 3.14 required')
PY
getent group stacksense-worker >/dev/null || groupadd --system stacksense-worker
getent group stacksense-artifacts >/dev/null || groupadd --system stacksense-artifacts
getent group stacksense-artifact-read >/dev/null || groupadd --system stacksense-artifact-read
getent group stacksense-artifact-gc >/dev/null || groupadd --system stacksense-artifact-gc
id stacksense-worker >/dev/null 2>&1 || useradd --system --gid stacksense-worker --no-create-home --home-dir /nonexistent --shell /usr/sbin/nologin stacksense-worker
id stacksense-artifacts >/dev/null 2>&1 || useradd --system --gid stacksense-artifacts --no-create-home --home-dir /nonexistent --shell /usr/sbin/nologin stacksense-artifacts
test "$(id -u stacksense-worker)" -ne "$(id -u stacksense-artifacts)"
usermod -a -G stacksense-artifact-read stacksense-worker
install -d -o root -g root -m 0755 "$dest" "$dest/bin" "$dest/layout_runtime" "$dest/deployment" "$dest/runtime/root/bin" "$dest/runtime/root/app"
install -o root -g root -m 0555 "$node" "$dest/runtime/root/bin/node"
test -f "$(dirname "$node")/../LICENSE"
install -o root -g root -m 0444 "$(dirname "$node")/../LICENSE" "$dest/runtime/NOTICE.node.txt"
install -o root -g root -m 0555 "$bwrap" "$dest/bin/bwrap"
install -o root -g root -m 0444 "$source_dir/deployment/LICENSE.bubblewrap.txt" "$dest/runtime/NOTICE.bubblewrap.txt"
test "$("$dest/runtime/root/bin/node" --version)" = v24.22.3
test "$("$dest/bin/bwrap" --version)" = 'bubblewrap 0.12.0'
# Minimal loader/library closure from the verified official Node executable.
# No whole-host /usr, home, credential or repository mounts are permitted.
ldd "$dest/runtime/root/bin/node" | awk '/=> \/|^\s*\// {for(i=1;i<=NF;i++) if($i ~ /^\//) print $i}' | while IFS= read -r library; do
  test -f "$library"
  install -D -o root -g root -m 0555 "$library" "$dest/runtime/root$library"
done
install -o root -g root -m 0444 "$source_dir/layout_runtime/elk_layout.mjs" "$dest/runtime/root/app/elk_layout.mjs"
install -o root -g root -m 0444 "$source_dir/layout_runtime/launch_elk.py" "$dest/layout_runtime/launch_elk.py"
install -o root -g root -m 0444 "$source_dir/layout_runtime/launch_probe.py" "$dest/layout_runtime/launch_probe.py"
install -o root -g root -m 0444 "$source_dir/layout_runtime/parent_probe.py" "$dest/layout_runtime/parent_probe.py"
install -o root -g root -m 0444 "$source_dir/layout_runtime/proof_probe.mjs" "$dest/runtime/root/app/proof_probe.mjs"
install -o root -g root -m 0444 "$source_dir/layout_runtime/seccomp_policy.json" "$dest/layout_runtime/seccomp_policy.json"
test -f "$source_dir/layout_runtime/node_modules/elkjs/lib/elk.bundled.js"
install -d -m 0755 "$dest/runtime/root/app/node_modules/elkjs/lib"
install -m 0444 "$source_dir/layout_runtime/node_modules/elkjs/lib/elk.bundled.js" "$dest/runtime/root/app/node_modules/elkjs/lib/elk.bundled.js"
# Copy complete installed package notices, not only the executable bundle.
for notice in LICENSE.md LICENSE README.md package.json; do
  if test -f "$source_dir/layout_runtime/node_modules/elkjs/$notice"; then
    install -m 0444 "$source_dir/layout_runtime/node_modules/elkjs/$notice" "$dest/runtime/root/app/node_modules/elkjs/$notice"
  fi
done
test "$(findmnt -no FSTYPE -T /var/lib/stacksense/diagrams)" = ext4 || test "$(findmnt -no FSTYPE -T /var/lib/stacksense/diagrams)" = xfs || { echo 'Mount approved ext4/XFS store before provisioning' >&2; exit 78; }
install -d -o stacksense-artifacts -g stacksense-artifact-read -m 2750 /var/lib/stacksense/diagrams /var/lib/stacksense/diagrams/sealed
install -d -o stacksense-artifacts -g stacksense-artifacts -m 0700 /var/lib/stacksense/diagrams/locks
install -d -o stacksense-worker -g stacksense-worker -m 0700 /var/lib/stacksense/diagrams/staging
install -d -o stacksense-worker -g stacksense-worker -m 0700 /var/lib/stacksense/diagram-b1-evidence
setfacl -m u:stacksense-artifacts:rx /var/lib/stacksense/diagrams/staging
setfacl -m d:u:stacksense-artifacts:rx /var/lib/stacksense/diagrams/staging
install -o root -g root -m 0555 "$source_dir/deployment/seal-generation" "$dest/seal-generation"
install -o root -g root -m 0555 "$source_dir/deployment/gc-generation" "$dest/gc-generation"
visudo -cf "$source_dir/deployment/diagram-artifacts.sudoers"
install -o root -g root -m 0440 "$source_dir/deployment/diagram-artifacts.sudoers" /etc/sudoers.d/stacksense-diagram-artifacts
# Runtime lock is generated only from actual installed bytes, not guessed here.
"$dest/venv/bin/python" -I - "$dest" <<'PY'
import hashlib,json,os,sys
from pathlib import Path
root=Path(sys.argv[1])
files=[]
for parent in (root/'bin',root/'layout_runtime',root/'runtime'/'root'):
    for path in sorted(parent.rglob('*')):
        if path.is_symlink(): raise SystemExit('symlink in runtime closure')
        if path.is_file():
            files.append({'path':str(path.relative_to(root)),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
payload={'version':'1.0.0','node':'24.22.3','bubblewrap':'0.12.0','elkjs':'0.12.1','files':files}
target=root/'deployment'/'runtime-lock.json'
fd=os.open(target,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o444)
with os.fdopen(fd,'w') as stream:
    json.dump(payload,stream,sort_keys=True,separators=(',',':'));stream.flush();os.fsync(stream.fileno())
PY
echo 'Installation staged only: install root-owned application package, least-privilege DB configs and existing-worker cgroup delegation; execute BOTH B1 proof suites before any registration/publication.'
