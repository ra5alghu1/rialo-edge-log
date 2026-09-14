#!/usr/bin/env bash
set -euo pipefail

if [[ ${EUID} -ne 0 ]]; then
  echo "Run this installer with sudo." >&2
  exit 1
fi

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo_root=$(cd -- "${script_dir}/../.." && pwd)
service_user=${RIALO_EDGE_USER:-rialo-edge}
state_root=/var/lib/rialo-edge-log
config_root=/etc/rialo-edge-log

if ! getent group "${service_user}" >/dev/null; then
  groupadd --system "${service_user}"
fi
if ! id "${service_user}" >/dev/null 2>&1; then
  useradd --system --gid "${service_user}" --groups dialout \
    --home-dir "${state_root}" --create-home --shell /usr/sbin/nologin \
    "${service_user}"
else
  usermod --append --groups dialout "${service_user}"
fi

install -d -o "${service_user}" -g "${service_user}" -m 0750 \
  "${state_root}" "${state_root}/data" "${state_root}/secrets"
install -d -o root -g "${service_user}" -m 0750 "${config_root}"

python3 -m venv "${repo_root}/.venv"
"${repo_root}/.venv/bin/python" -m pip install --upgrade pip
"${repo_root}/.venv/bin/python" -m pip install -r "${repo_root}/gateway/requirements.txt"

if [[ ! -f "${config_root}/edge.env" ]]; then
  install -o root -g "${service_user}" -m 0640 \
    "${script_dir}/rialo-edge.env.example" "${config_root}/edge.env"
  echo "Created ${config_root}/edge.env; edit its placeholders before starting services."
else
  echo "Preserved existing ${config_root}/edge.env."
fi

for source in "${script_dir}"/*.service; do
  destination="/etc/systemd/system/$(basename -- "${source}")"
  sed \
    -e "s|@REPO_ROOT@|${repo_root}|g" \
    -e "s|@SERVICE_USER@|${service_user}|g" \
    "${source}" >"${destination}"
  chmod 0644 "${destination}"
done

systemctl daemon-reload
echo "Linux edge services installed but not enabled or started."
echo "Next: edit ${config_root}/edge.env, install the Rialo CLI for ${service_user}, and test the serial gateway."
