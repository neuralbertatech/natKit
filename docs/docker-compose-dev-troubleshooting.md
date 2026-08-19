# Docker Compose development troubleshooting

Command:

```powershell
docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build
```

## 1. Docker Desktop Linux engine unavailable

**Error**

```text
open //./pipe/dockerDesktopLinuxEngine: The system cannot find the file specified
```

**Cause**

Docker Desktop's Linux engine was not running, so the Docker CLI could not reach
the daemon.

**Resolution**

Started Docker Desktop and waited for the Linux engine to become available.
`docker compose` then connected successfully and began building the images.

## 2. Linux build script checked out with CRLF endings

**Error**

```text
/libnatkit/scripts/install_librdkafka.sh: line 2: $'\r': command not found
/libnatkit/scripts/install_librdkafka.sh: line 19: syntax error: unexpected end of file
```

The failed script did not install librdkafka, which subsequently caused CMake to
report that `/libnatkit/build/include` did not exist.

**Cause**

`libnatkit/scripts/install_librdkafka.sh` had Windows CRLF line endings but runs
inside a Linux build container.

**Resolution**

Converted the script to LF endings and added a `.gitattributes` rule at the
root of the `libnatkit` submodule:

```gitattributes
*.sh text eol=lf
```

This also keeps shell scripts LF-normalized on future Windows checkouts.

## 3. Vendored librdkafka configure script retained CRLF endings

**Error**

```text
/usr/bin/env: 'bash\r': No such file or directory
./Makefile.config missing: please run ./configure
```

**Cause**

After fixing the wrapper script, its nested
`third-party/librdkafka/configure` entrypoint and sourced helpers such as
`mklove/modules/configure.base` were also found to have CRLF line endings.
Several vendored build files were affected by the Windows checkout.

**Resolution**

Added a bridge-image build step that strips trailing carriage returns from text
files under `scripts` and `third-party/librdkafka` before CMake invokes them;
binary files are explicitly skipped. The submodule's `.gitattributes` also
enforces LF for shell entrypoints and librdkafka's `mklove` helpers on future
clean checkouts. The installer now exits immediately when a nested command
fails, avoiding misleading downstream CMake errors.

## 4. CRLF normalization initially covered only the bridge image

**Error**

```text
[natkit-v0-ml-control-plane] /usr/bin/env: 'bash\r': No such file or directory
```

**Cause**

The bridge, backend, and ML control-plane images copy `libnatkit` through
separate Dockerfiles and build contexts. Fixing the bridge image did not alter
the files copied into the other images.

**Resolution**

Added the same binary-safe text normalization step to
`Dockerfile_natkit_backend` and `Dockerfile_natkit_ml_control_plane`. The bridge
image was rebuilt independently and completed successfully before retrying the
full stack.

## 5. Optional remote ML worker restarted without credentials

**Error**

```text
RuntimeError: shared auth is required; provide --auth-session-token or
--auth-username/--auth-password
```

**Cause**

`natkit-v0-ml-worker-a` is an external worker that must authenticate against a
real account in the shared auth database. This checkout had no `.env` file, so
`NATKIT_ML_WORKER_AUTH_USERNAME` and `NATKIT_ML_WORKER_AUTH_PASSWORD` were empty.
The control plane already starts embedded worker slots, making the external
worker optional for ordinary local development.

**Resolution**

Placed the external worker behind the `ml-worker` Compose profile. The normal
development command now starts without a credential-related restart loop. To
exercise the external worker, create an account, put these ignored values in
`.env`, and enable its profile:

```dotenv
NATKIT_ML_WORKER_AUTH_USERNAME=<real-account-username>
NATKIT_ML_WORKER_AUTH_PASSWORD=<real-account-password>
```

```powershell
docker compose -f docker-compose.yml -f docker-compose.dev.yml --profile ml-worker up --build
```
