#pragma once

#include <concepts>
#include <span>
#include <string>
#include <vector>
#include <set>

namespace natKit {

template <typename T>
concept ObjectWithToStringFunction = requires(const T& t) { t.toString(); };

template <ObjectWithToStringFunction T>
std::string toString(const T& t) {
  return t.toString();
}

template <typename T>
requires std::integral<T> || std::floating_point<T>
std::string toString(const T& t) {
  return std::to_string(t);
}

template <typename T>
requires std::convertible_to<T, std::string>
std::string toString(const T& t) {
  return static_cast<std::string>(t);
}

//template <typename T>
//std::string toString(const std::span<T>& span) {
//  std::string string = "[";
//  for (int i = 0; i < span.size(); ++i) {
//    string.append(toString(span[i]));
//    if (i < (span.size() - 1)) {
//      string.append(", ");
//    }
//  }
//  string.append("]");
//  return string;
//}

template <typename Iterator>
std::string toString(const Iterator& begin, const Iterator& end) {
  Iterator it = begin;
  Iterator next = begin;
  std::string string = "";
  if (next != end) {
    next = std::next(next);
  }

  while (it != end) {
    if (next != end) {
      string.append(toString(*it) + ", ");
      it = next;
      next = std::next(next);
    } else {
      string.append(toString(*it));
      it = next;
    }
  }

  return string;
}

template <typename T>
std::string toString(const std::vector<T>& vec) {
  return "[" + toString(vec.begin(), vec.end()) + "]";
}

template <typename T>
std::string toString(const std::set<T>& set) {
  return "{" + toString(set.begin(), set.end()) + "}";
}

}
