import os


PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))


def add_subproject_src_to_path(subprojects):
    for subproject in subprojects:
        __path__.append(
            os.path.join(PROJECT_ROOT, subproject, "src", "python", "natKit")
        )


def add_subproject_build_to_path(subprojects):
    for subproject in subprojects:
        __path__.append(
            os.path.join(PROJECT_ROOT, subproject, "build", "python", "natKit")
        )


add_subproject_build_to_path(["api"])

add_subproject_src_to_path(
    [
        "api",
        "client",
        "common",
        "server",
    ]
)

from natKit.common.util import global_variables

global_variables.register("PROJECT_ROOT", PROJECT_ROOT)
