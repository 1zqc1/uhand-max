#ifndef _HW_ACTION_CTL_
#define _HW_ACTION_CTL_

#include <stdint.h>

// 手指角度目标结构
typedef struct {
  uint8_t thumb;
  uint8_t index;
  uint8_t middle;
  uint8_t ring;
  uint8_t pinky;
} FingerAngles;

// 平滑控制参数结构
typedef struct {
  FingerAngles current;
  FingerAngles target;
  uint16_t step_interval;
  uint32_t last_update;
} SmoothControl;

#endif