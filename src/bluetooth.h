#ifndef BLUETOOTH_H_
#define BLUETOOTH_H_

#include <Arduino.h>

#define FRAME_HEADER            0x55
#define CMD_SERVO_MOVE          0x03
#define CMD_ACTION_GROUP_RUN    0x06
#define CMD_ACTION_GROUP_STOP   0x07
#define CMD_ACTION_GROUP_SPEED  0x0B
#define CMD_GET_BATTERY_VOLTAGE 0x0F

#define BATTERY_VOLTAGE       0x0F
#define ACTION_GROUP_RUNNING  0x06
#define ACTION_GROUP_STOPPED  0x07
#define ACTION_GROUP_COMPLETE 0x08

struct LobotServo {
  uint8_t  ID;
  uint16_t Position;
};

struct uHand_Servo{
  uint8_t num;
  uint16_t time;
  struct LobotServo servos[6];
};

struct blue_info{
  uint8_t rec_num;
  uint8_t func;
  uint8_t buf[128];
};

class blue_controller
{
  public:
    blue_controller();

    void receiveHandle(void);
    bool get_servos(struct uHand_Servo* uhand_servos);

  private:
    struct blue_info rec_oj;
    struct blue_info resule_oj;
    uint8_t success;
};

#endif