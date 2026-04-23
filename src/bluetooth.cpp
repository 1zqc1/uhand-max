#include "bluetooth.h"

blue_controller::blue_controller()
{
  success = 0;
}

bool blue_controller::get_servos(struct uHand_Servo* uhand_servos)
{
  if(success == 0)
    return false;
  success = 0;
  if(resule_oj.func == CMD_SERVO_MOVE)
  {
    uhand_servos->num = resule_oj.buf[0];
    uhand_servos->time = (resule_oj.buf[2] << 8) | resule_oj.buf[1];
    for(int i = 0 ; i < uhand_servos->num ; i++)
    {
      uhand_servos->servos[i].ID = resule_oj.buf[i*3+3];
      uhand_servos->servos[i].Position = (resule_oj.buf[i*3+5] << 8) | resule_oj.buf[i*3+4];
    }
    return true;
  }else{
    Serial.print("func:");
    Serial.println(resule_oj.func);
    return false;
  }
}

/* 0x55 0x55 number func (...info...) */
void blue_controller::receiveHandle(void)
{
  static uint8_t step = 0;
  static uint8_t head_count = 0;
  static uint8_t data_count = 0;
  while (Serial.available() > 0)
  {
    char rx = Serial.read();
    switch(step)
    {
      case 0:
        if(rx == FRAME_HEADER)
        {
          head_count++;
          if(head_count > 1)
          {
            step++;
            head_count = 0;
          }
        }else{
          head_count = 0;
        }
        break;
      case 1:
        if(rx >= 0 && rx < 128)
        {
          rec_oj.rec_num = rx;
          step++;
        }else{
          step = 0;
        }
        break;
      case 2:
        if(rx > 0)
        {
          rec_oj.func = rx;
          step++;
        }else{
          step = 0;
        }
        break;
      case 3:
        rec_oj.buf[data_count] = rx;
        data_count++;
        if(data_count > rec_oj.rec_num - 2)
        {
          resule_oj.rec_num = rec_oj.rec_num;
          resule_oj.func = rec_oj.func;
          memcpy(resule_oj.buf , rec_oj.buf , rec_oj.rec_num -2);
          success = 1;
          data_count = 0;
          step = 0;
        }
        break;
      default:
        Serial.println("-def-");
        step = 0;
        break;
    }
  }
}