<img src="https://neuralberta.tech/images/event/natHACKs/nathanGlow.png" height="250">

# natKit

This is a collection of tools created to help jumpstart users on working with BCI hardware. By providing ways to connect, process, and visulize data from various peices of hardware.


## Installation

### Requirements

- [Docker](https://docs.docker.com/get-docker/)
- [Protoc](https://grpc.io/docs/protoc-installation/)
- [Python](https://www.python.org/downloads/) 3.9 or above
- [virtualenv](https://docs.python.org/3/library/venv.html)


### From Source

Clone the repository:
```sh
git clone https://github.com/neuralbertatech/natKit
cd natKit
```

Create a virtual environment to install the dependencies:
```sh
python -m venv <Environment-Name>  # For example  $ python -m venv .venv
```

Activate the virtual environment and install the dependencies (Platform-Specific):
#### MacOS and Linux
```sh
source ./<Environment-Name>/bin/activate  # source ./.venv/bin/activate
pip install -r requirements.txt
```

### Windows (Powershell)
```sh
./<Environment-Name>/Scripts/Activate.ps1
pip install -r requirements.txt
```

Build the Protobuf code:
#### MacOs and Linux
```sh
./build.sh
```

Start the docker server:
```sh
docker compose up -d
```

## Getting Started

Now to get started go to the bin/ folder and run some scripts, for example:
```sh
python ./bin/muse2-producer.py &
python ./bin/stream-visulizer-gui.py
```

## Additional Configuration

### Docker Server

If your docker server is running on a remote machine (or a different port on the same machine), you can configure the connection parameters using the environment variables:
- `NATKIT_SERVER` for the server address
- `NATKIT_SERVER_PORT` for the server port

For example if you had the server running on a machine located at `192.168.0.12` on port `1234` you would set the environment variables with:
```sh
export NATKIT_SERVER="192.168.0.12"
export NATKIT_SERVER_PORT="1234"
```
