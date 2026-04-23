//Action group file
#ifndef ACTIONS_H
#define ACTIONS_H
#include <Arduino.h>
#define action_count 3

// 动作数据（在 .ino 中定义，.cpp 通过 extern 访问）
extern uint8_t action[action_count][7];

#endif