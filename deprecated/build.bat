if not exist ".\natKit\api\build\python\natKit\codegen\api" mkdir .\natKit\api\build\python\natKit\codegen\api
copy /b .\natKit\api\build\python\natKit\__init__.py +,,
copy /b .\natKit\api\build\python\natKit\codegen\__init__.py +,,
copy /b .\natKit\api\build\python\natKit\codegen\api\__init__.py +,,
protoc -I=".\natKit\api\src\proto\natKit\api\" --python_out=".\natKit\api\build\python\natKit\codegen\api\" --proto_path=".\natKit\api\src\proto\natKit\api\" schema.proto
