#pragma once

#include <variant>

namespace natKit {

template <typename ValueType, typename ErrorType>
class Result {
  const std::variant<ValueType, ErrorType> value;
  const bool success;

  Result(std::variant<ValueType, ErrorType> val, bool success) : value(val), success(success) {}

  public:
    static Result ok(const ValueType& val) {
      return Result(std::variant<ValueType, ErrorType>(std::in_place_index<0>, val), true);
    }

    static Result err(const ErrorType& err) {
      return Result(std::variant<ValueType, ErrorType>(std::in_place_index<1>, err), false);
    }

    bool isOk() const {
      return success;
    }

    bool isErr() const {
      return not success;
    }

    ValueType getValue() const {
      return std::get<0>(value);
    }

    ErrorType getError() const {
      return std::get<1>(value);
    }
};

template <typename T>
class Ok {
  const T val;
  public:
    Ok(const T& val) : val(val) {}

    template<typename U>
    operator Result<T, U>() const {
      return Result<T, U>::ok(val);
    }
};

template <typename T>
class Err {
  const T val;
  public:
    Err(const T& val) : val(val) {}

    template<typename U>
    operator Result<U, T>() const {
      return Result<U, T>::err(val);
    }
};

}
