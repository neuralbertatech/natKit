#include <catch2/catch_test_macros.hpp>
#include <common/cxx/util/result.hpp>

namespace natKit {

TEST_CASE("Test Ok", "[Result]") {
  REQUIRE(Result<int, std::string>::ok(1).isOk());
}

TEST_CASE("Test Err", "[Result]") {
  REQUIRE(Result<int, std::string>::err("Failed").isErr());
}

TEST_CASE("Test getValue", "[Result]") {
  REQUIRE(20 == Result<int, std::string>::ok(20).getValue());
}

TEST_CASE("Test getError", "[Result]") {
  REQUIRE("Failed" == Result<int, std::string>::err("Failed").getError());
}

TEST_CASE("Test getValue throws on err", "[Result]") {
  REQUIRE_THROWS(20 == Result<int, std::string>::err("Failed").getValue());
}

TEST_CASE("Test getError throws on ok", "[Result]") {
  REQUIRE_THROWS(20 == Result<int, std::string>::err("Failed").getValue());
}

TEST_CASE("Test identical ok and err types for ok", "[Result]") {
  REQUIRE(Result<int, int>::ok(20).isOk());
}

TEST_CASE("Test identical ok and err types for err", "[Result]") {
  REQUIRE(Result<int, int>::err(20).isErr());
}

TEST_CASE("Test Ok casting", "[Result]") {
  Result<int, std::string> result = Ok(10);
  REQUIRE(result.isOk());
}

TEST_CASE("Test Err casting", "[Result]") {
  Result<int, std::string> result = Err<std::string>("Hello");
  REQUIRE(result.isErr());
}

TEST_CASE("Test Ok casting when types are the same", "[Result]") {
  Result<int, int> result = Ok(10);
  REQUIRE(result.isOk());
}

TEST_CASE("Test Err casting when types are the same", "[Result]") {
  Result<int, int> result = Err(20);
  REQUIRE(result.isErr());
}

}
