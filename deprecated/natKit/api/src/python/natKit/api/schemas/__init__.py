from natKit.common.util import global_variables
global_variables.register("JSON_SCHEMA_PATH", global_variables.lookup("PROJECT_ROOT") + "/api/src/json/")

from .schema import *
from .simple_message_schema import *
from .basic_meta_info_schema import *

from .schema_registry import *

from .csv_schema import *
from .meta_schema import *
