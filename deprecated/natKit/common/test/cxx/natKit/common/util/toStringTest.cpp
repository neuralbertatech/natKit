#include <catch2/catch_test_macros.hpp>
#include <common/cxx/util/toString.hpp>

namespace natKit {

TEST_CASE("Test Empty Vector", "[toString]") {
  const std::vector<int> vec = {};
  const std::string expectedString = "[]";
  const auto actualString = toString(vec);
  REQUIRE(expectedString == actualString);
}

TEST_CASE("Test Single-Element Vector", "[toString]") {
  const std::vector<int> vec = {1};
  const std::string expectedString = "[1]";
  const auto actualString = toString(vec);
  REQUIRE(expectedString == actualString);
}

TEST_CASE("Test Standard Vector", "[toString]") {
  const std::vector<int> vec = {1, 2, 3, 4, 5};
  const std::string expectedString = "[1, 2, 3, 4, 5]";
  const auto actualString = toString(vec);
  REQUIRE(expectedString == actualString);
}

TEST_CASE("Test Standard Set", "[toString]") {
  const std::set<int> set = {1, 2, 3, 4, 5};
  const std::string expectedString = "{1, 2, 3, 4, 5}";
  const auto actualString = toString(set);
  REQUIRE(expectedString == actualString);
}

TEST_CASE("Test Int", "[toString]") {
  REQUIRE("1" == toString(1));
}

TEST_CASE("Test String", "[toString]") {
  REQUIRE("Hello" == toString("Hello"));
}

TEST_CASE("Test Float", "[toString]") {
  REQUIRE("3.14" == toString(3.14).substr(0, 4)); // Ignore 0's at the end
}

}
