#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CUDA_REQUIREMENTS_FILE="${ROOT_DIR}/requirements-cuda-cu121.txt"

if [[ -z "${CONDA_PREFIX:-}" ]]; then
  echo "Activate the target conda environment first, e.g. 'conda activate stocks'." >&2
  exit 1
fi

PYTHON_BIN="${CONDA_PREFIX}/bin/python"
if [[ ! -x "${PYTHON_BIN}" ]]; then
  echo "Active conda environment does not expose ${PYTHON_BIN}." >&2
  exit 1
fi

if ! command -v nvidia-smi >/dev/null 2>&1; then
  echo "nvidia-smi is not available in this shell. This helper expects WSL GPU support." >&2
  exit 1
fi

ACTIVATE_D="${CONDA_PREFIX}/etc/conda/activate.d"
DEACTIVATE_D="${CONDA_PREFIX}/etc/conda/deactivate.d"
ACTIVATE_HOOK="${ACTIVATE_D}/wsl_cuda.sh"
DEACTIVATE_HOOK="${DEACTIVATE_D}/wsl_cuda.sh"

echo "Installing driver-compatible CUDA PyTorch wheels into ${CONDA_PREFIX}..."
"${PYTHON_BIN}" -m pip install --upgrade -r "${CUDA_REQUIREMENTS_FILE}"

mkdir -p "${ACTIVATE_D}" "${DEACTIVATE_D}"

cat > "${ACTIVATE_HOOK}" <<'EOF'
#!/usr/bin/env bash
# Ensure WSL GPU driver libraries are visible to CUDA-aware Python packages.
export _STOCKS_OLD_LD_LIBRARY_PATH="${LD_LIBRARY_PATH-}"
case ":${LD_LIBRARY_PATH-}:" in
  *:/usr/lib/wsl/lib:*) ;;
  *) export LD_LIBRARY_PATH="/usr/lib/wsl/lib${LD_LIBRARY_PATH:+:${LD_LIBRARY_PATH}}" ;;
esac
EOF

cat > "${DEACTIVATE_HOOK}" <<'EOF'
#!/usr/bin/env bash
if [ "${_STOCKS_OLD_LD_LIBRARY_PATH+x}" = x ]; then
  export LD_LIBRARY_PATH="${_STOCKS_OLD_LD_LIBRARY_PATH}"
  unset _STOCKS_OLD_LD_LIBRARY_PATH
else
  unset LD_LIBRARY_PATH
fi
EOF

chmod +x "${ACTIVATE_HOOK}" "${DEACTIVATE_HOOK}"

if "${PYTHON_BIN}" -m pip show marker-pdf >/dev/null 2>&1 || "${PYTHON_BIN}" -m pip show surya-ocr >/dev/null 2>&1; then
  echo "Warning: marker-pdf and surya-ocr currently require newer torch builds than this WSL-safe cu121 profile." >&2
  echo "Keep OCR tooling in a separate environment if you need those packages." >&2
fi

echo "WSL CUDA bootstrap complete."
echo "Reactivate the conda environment to pick up /usr/lib/wsl/lib automatically:"
echo "  conda deactivate && conda activate \"$(basename "${CONDA_PREFIX}")\""
