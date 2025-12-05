#!/usr/bin/env bash

SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
PROJECT_ROOT=${SCRIPT_DIR}

VENV_NAME="${1:-.venv}"
VENV_PATH=${PROJECT_ROOT}/${VENV_NAME}

function setup_venv() {
  echo ${VENV_PATH}
  if [ ! -d "./${VENV_PATH}" ]
  then
    python -m venv ${VENV_NAME}
  fi
  
  source ${VENV_PATH}/bin/activate
}

function install_dependancies() {
  pip install -r ${PROJECT_ROOT}/requirements.txt
  pre-commit install
}


setup_venv
install_dependancies
