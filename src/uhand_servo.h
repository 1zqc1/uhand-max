#ifndef _HW_ACTION_CTL_
#define _HW_ACTION_CTL_
#include "actions.h"
#include "bluetooth.h"

class HW_ACTION_CTL{
  public:
    uint8_t extended_func_angles[6] = { 180,180,180,180,180, 90 };  // 初始化：张开
    void action_set(int num);
    int action_state_get(void);
    void action_task(void);

    // 蓝牙控制任务
    void blue_task(void);
    void blue_ctl_receive(void);
    bool blue_get_servos(struct uHand_Servo* uhand_servos);

  private:
    int action_num = 0;
};

#endif