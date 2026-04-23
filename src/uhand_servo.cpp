#include "uhand_servo.h"
#include "bluetooth.h"

// 蓝牙接收对象
blue_controller blue_ctl;
// 蓝牙数据存储
struct uHand_Servo uhand_servos;

void HW_ACTION_CTL::action_set(int num){
  action_num = num;
}

int HW_ACTION_CTL::action_state_get(void){
  return action_num;
}

//执行单一动作时使用
void HW_ACTION_CTL::action_task(void){
  if(action_num != 0 && action_num <= action_count)
  {
    extended_func_angles[0] = action[action_num-1][1];
    extended_func_angles[1] = action[action_num-1][2];
    extended_func_angles[2] = action[action_num-1][3];
    extended_func_angles[3] = action[action_num-1][4];
    extended_func_angles[4] = action[action_num-1][5];
    extended_func_angles[5] = action[action_num-1][6];

    // 清空动作变量
    action_num = 0;
  }
}

// 蓝牙接收并解析
void HW_ACTION_CTL::blue_ctl_receive(void)
{
  blue_ctl.receiveHandle();
}

// 蓝牙控制任务
void HW_ACTION_CTL::blue_task(void)
{
  bool rt = blue_ctl.get_servos(&uhand_servos);
  if(rt)
  {
    for(int i = 0; i < uhand_servos.num ; i++)
    {
      switch(uhand_servos.servos[i].ID)
      {
        case 1: // 大拇指，转动角度相反
          extended_func_angles[uhand_servos.servos[i].ID - 1] = map(uhand_servos.servos[i].Position , 1100 , 1950 , 180 , 0);
          break;

        case 2: // 食指 ~ 小拇指
        case 3:
        case 4:
        case 5:
          extended_func_angles[uhand_servos.servos[i].ID - 1] = map(uhand_servos.servos[i].Position , 1100 , 1950 , 0, 180);
          break;

        case 6: // 云台转动
          extended_func_angles[uhand_servos.servos[i].ID - 1] = map(uhand_servos.servos[i].Position , 600 , 2400 , 0, 180);
          break;
      }
    }
  }
}