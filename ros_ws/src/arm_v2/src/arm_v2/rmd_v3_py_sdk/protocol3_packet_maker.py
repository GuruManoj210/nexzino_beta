#!/usr/bin/env python
# -*- coding: utf-8 -*-

########################################################
# This file have all the functions of the RMD_V3
########################################################

from .rmd_dcl import *
from .can_handler import *
import can


class RMD3(RMD_dcl, CAN_Handler):
    def __init__(self, bustype="socketcan", channel="can0", bitrate=1000000):
        CAN_Handler.__init__(self, bustype, channel, bitrate)
        self.bus = can.interface.Bus(bustype=bustype, channel=channel, bitrate=bitrate)

    # Read The PID Prameters 0x30
    def RD_PID_Data(self):
        data = [0x30, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]
        return data

    # Write PID parameter to RAM command 0x31
    def WR_PID_RAM(self, PositionKP, PositionKi, SpeedKp, SpeedKi, TorqueKp, TorqueKi):
        data = [
            0x31,
            0x00,
            TorqueKp,
            TorqueKi,
            SpeedKp,
            SpeedKi,
            PositionKP,
            PositionKi,
        ]
        return data

    # Write PID parameter to ROM command 0x32
    def WR_PID_ROM(self, PositionKP, PositionKi, SpeedKp, SpeedKi, TorqueKp, TorqueKi):
        data = [
            0x32,
            0x00,
            TorqueKp,
            TorqueKi,
            SpeedKp,
            SpeedKi,
            PositionKP,
            PositionKi,
        ]
        return data

    # Read acceleration data command 0x42
    def RD_Acceleration_Data(self):
        data = [0x42, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]
        return data

    # Write acceleration data to RAM command 0x43
    def WR_Acceleration_Data(self, Acceleration):
        Acceleration = bytearray.fromhex(f"{(hex(int(abs(Acceleration)))[2:]):0>8}")
        data = [
            0x43,
            0x00,
            0x00,
            0x00,
            Acceleration[3],
            Acceleration[2],
            Acceleration[1],
            Acceleration[0],
        ]
        return data

    # Read Multi-Turn Encoder Position Command 0x60
    def RD_Multi_Turn_Position(self):
        data = [0x60, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]
        return data

    # Read Multi-Turn Encoder Original Position Command 0x61
    def RD_Multi_Turn_Original_Position(self):
        data = [0x61, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]
        return data

    # Read Multi-Turn Encoder Zero Offset Command 0x62
    def RD_Multi_Turn_Encoder_Zero_Offset(self):
        data = [0x62, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]
        return data

    # Write Multi Turn Value as Zero Position to ROM (Need to Restart after the Command) 0x63
    def WR_multi_turn_as_Zero_ROM(self, Multi_turn_value):
        Value = bytearray.fromhex(
            f"{(Signed_int_to_hex((int(Multi_turn_value)), 32)[2:]):0>8}"
        )
        data = [0x63, 0x00, 0x00, 0x00, Value[3], Value[2], Value[1], Value[0]]
        return data

    # Write Current Multi Turn Value as Zero Position to ROM(Need to Restart after the Command) 0x64
    def WR_Current_multi_turn_as_Zero_ROM(self):
        data = [0x64, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]
        return data

    # Read Multi-Turn Angle Command 0x92
    def RD_Multi_Turn_Angle(self):
        data = [0x92, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]
        return data

    # Read motor status 1 (Temperature, Brake, Voltage, error flag) commands 0x9A
    def RD_Motor_status_1(self):
        data = [0x9A, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]
        return data

    # Read motor status 2 (Temperature, Current, Speed, Angle) commands 0x9C
    def RD_Motor_status_2(self):
        data = [0x9C, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]
        return data

    # Read motor status 3 (Temperature, Current of A, B, C) commands 0x9D
    def RD_Motor_status_3(self):
        data = [0x9D, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]
        return data

    # Motor Shutdown Command(Turn OFF the motor and clears the motor running status) 0x80
    def Motor_shutdown(self):
        data = [0x80, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]
        return data

    # Motor Stop Command(Pause the Motor) 0x81
    def Motor_Stop(self):
        data = [0x81, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]
        return data

    # Torque current control command 0xA1
    def Torque_Ctrl_Mode(self, Current):
        Current = bytearray.fromhex(
            f"{(Signed_int_to_hex((int(Current*100)), 16)[2:]):0>4}"
        )
        data = [0xA1, 0x00, 0x00, 0x00, Current[1], Current[0], 0x00, 0x00]
        return data

    # Speed control command 0xA2
    def Speed_Ctrl_Mode(self, Speed):
        Speed_SA1 = bytearray.fromhex(
            f"{(Signed_int_to_hex((int(Speed*100)), 32)[2:]):0>8}"
        )
        data = [
            0xA2,
            0x00,
            0x00,
            0x00,
            Speed_SA1[3],
            Speed_SA1[2],
            Speed_SA1[1],
            Speed_SA1[0],
        ]
        return data

    # Absolute Position Closed-loop Control Command 0XA4
    def Absolute_Position_ctrl(self, Speed, Angle):
        Angle = bytearray.fromhex(
            f"{(Signed_int_to_hex((int(Angle*100)), 32)[2:]):0>8}"
        )
        Speed = bytearray.fromhex(f"{(Signed_int_to_hex((int(Speed)), 16)[2:]):0>4}")
        data = [0xA4, 0x00, Speed[1], Speed[0], Angle[3], Angle[2], Angle[1], Angle[0]]
        return data

    # Incremental Position Control Command 0XA8
    def Incremental_position_ctrl(self, Speed, Angle):
        Angle = bytearray.fromhex(
            f"{(Signed_int_to_hex((int(Angle*100)), 32)[2:]):0>8}"
        )
        Speed = bytearray.fromhex(f"{(Signed_int_to_hex((int(Speed)), 16)[2:]):0>4}")
        data = [0xA8, 0x00, Speed[1], Speed[0], Angle[3], Angle[2], Angle[1], Angle[0]]
        return data

    # Read Motor Mode 0x70
    def RD_Motor_Mode(self):
        data = [0x70, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]
        return data

    # Read Motor Power 0x71
    def RD_Motor_Power(self):
        data = [0x71, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]
        return data

    # System Reset 0x76
    def System_Reset(self):
        data = [0x76, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]
        return data

    # Brake Release 0x77
    def Motor_Brake_Release(self):
        data = [0x77, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]
        return data

    # Brake Command 0x78
    def Motor_Brake(self):
        data = [0x78, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]
        return data

    # Read System Runtime 0xB1
    def RD_System_Runtime(self):
        data = [0xB1, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]
        return data

    # Read System Version Date 0xB2
    def RD_Version_Date(self):
        data = [0xB2, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]
        return data

    # Set Communication Interruption Time in ms (Zero = Disables) 0xB3
    def Set_Comm_Interruption_time(self, Time):
        Time = bytearray.fromhex(f"{(hex(int(abs(Time)))[2:]):0>8}")
        data = [0xB3, 0x00, 0x00, 0x00, Time[3], Time[2], Time[1], Time[0]]
        return data

    # Set Baudrate(0=500Kbps 1=1Mbps) (There won't be any reply for this command) 0xB4
    def Set_Baudrate(self, Baudrate):
        if Baudrate == 0 or Baudrate == 1:
            Baudrate = bytearray.fromhex(f"{(hex(int(Baudrate))[2:]):0>2}")
            data = [0xB4, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, Baudrate[0]]
            return data
        else:
            print("Value should be 0 or 1, (0=500Kbps 1=1Mbps)")

    # Make the CAN Message
    def TX_Packet(self, motor_ID, send_data):
        if motor_ID < 0 or send_data == None:
            print("Enter the Right ID or data")
        else:
            motor_ID = int(motor_ID)
            return can.Message(
                arbitration_id=320 + motor_ID, data=send_data, is_extended_id=False
            )

    # Function to send and receive the CAN Frame
    def Send_Receive_Message(self, TX_Packet):
        self.Send_Message(TX_Packet)
        while True:
            Temp_mesgrecv = self.Receive_Message()
            if (
                (TX_Packet.arbitration_id) + 0x100
            ) == Temp_mesgrecv.arbitration_id and (
                TX_Packet.data[0]
            ) == Temp_mesgrecv.data[
                0
            ]:
                RX_Packet = Temp_mesgrecv
                self.decode_mesgrecv(RX_Packet)
                break

    # This Function includes send and Receive functions as well. Connect only 1 servo.(ID should be in between 1-32) 0x79
    def Set_CAN_ID(self, ID):
        ID = bytearray.fromhex(f"{(hex(int(abs(ID)))[2:]):0>2}")
        data = [0x79, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, ID[0]]
        TX_Packet = can.Message(arbitration_id=0x300, data=data, is_extended_id=False)
        self.Send_Message(TX_Packet)
        while True:
            Temp_mesgrecv = self.Receive_Message()
            if (TX_Packet.arbitration_id == Temp_mesgrecv.arbitration_id) and (
                TX_Packet.data[0] == Temp_mesgrecv.data[0]
            ):
                RX_Packet = Temp_mesgrecv
                print(RX_Packet)
                self.decode_mesgrecv(RX_Packet)
                break

    # This Function includes send and Receive functions as well. Connect only 1 servo.(ID should be in between 1-32) 0x79
    def Find_CAN_ID(self):
        data = [0x79, 0x00, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00]
        TX_Packet = can.Message(arbitration_id=0x300, data=data, is_extended_id=False)
        self.Send_Message(TX_Packet)
        while True:
            Temp_mesgrecv = self.Receive_Message()
            if (TX_Packet.arbitration_id == Temp_mesgrecv.arbitration_id) and (
                TX_Packet.data[0] == Temp_mesgrecv.data[0]
            ):
                RX_Packet = Temp_mesgrecv
                print(RX_Packet)
                self.decode_mesgrecv(RX_Packet)
                break

    # Function to Decode all the received Messages
    def decode_mesgrecv(self, Message):
        Array = [
            f"{(hex(Message.data[0])[2:]):0>2}",
            f"{(hex(Message.data[1])[2:]):0>2}",
            f"{(hex(Message.data[2])[2:]):0>2}",
            f"{(hex(Message.data[3])[2:]):0>2}",
            f"{(hex(Message.data[4])[2:]):0>2}",
            f"{(hex(Message.data[5])[2:]):0>2}",
            f"{(hex(Message.data[6])[2:]):0>2}",
            f"{(hex(Message.data[7])[2:]):0>2}",
        ]
        # Decode the Message of the Read PID Data 0x30
        # Decode the Message of PID Data After writing it to RAM 0x31
        # Decode the Message of PID Data After writing it to ROM 0x32
        if (
            Message.data[0] == 0x30
            or Message.data[0] == 0x31
            or Message.data[0] == 0x32
        ):
            if Message.data[0] == 0x30:
                print("Reading PID Data From Motor")
            elif Message.data[0] == 0x31:
                print("Wrote PID DATA to RAM")
            else:
                print("Wrote PID DATA to ROM")
            self.TORQUE_LOOP_KP = int(Array[2], 16)
            self.TORQUE_LOOP_KI = int(Array[3], 16)
            self.SPEED_LOOP_KP = int(Array[4], 16)
            self.SPEED_LOOP_KI = int(Array[5], 16)
            self.POSITION_LOOP_KP = int(Array[6], 16)
            self.POSITION_LOOP_KI = int(Array[7], 16)
            print(
                "Position loop Kp",
                self.POSITION_LOOP_KP,
                "\nPosition loop Ki",
                self.POSITION_LOOP_KI,
                "\nSpeed loop Kp",
                self.SPEED_LOOP_KP,
                "\nSpeed loop Ki",
                self.SPEED_LOOP_KI,
                "\nTorque loop Kp",
                self.TORQUE_LOOP_KP,
                "\nTorque loop Ki",
                self.TORQUE_LOOP_KI,
            )

        # Decode the Acceleration read Data 0x42
        # Decode the Acceleration Write Data 0x43
        elif Message.data[0] == 0x42 or Message.data[0] == 0x43:
            if Message.data[0] == 0x42:
                print("Reading Acceleration Data")
            else:
                print("Wrote Acceleration Data")
            self.ACCELERATION_IN = Signed_hex_to_int(
                (f"{Array[7]}{Array[6]}{Array[5]}{Array[4]}"), 32
            )
            print("Acceleration is", self.ACCELERATION_IN, "dps/s")

        # Decode Read multi turns position Message 0x60
        elif Message.data[0] == 0x60:
            self.MULTI_TURN_POSITION = Signed_hex_to_int(
                (f"{Array[7]}{Array[6]}{Array[5]}{Array[4]}"), 32
            )
            print("MULTI_TURN_POSITION =", self.MULTI_TURN_POSITION)

        # Decode Read multi turns Original position Message 0x61
        elif Message.data[0] == 0x61:
            self.ENCODER_ORIGINAL_POSITION = Signed_hex_to_int(
                (f"{Array[7]}{Array[6]}{Array[5]}{Array[4]}"), 32
            )
            print("Encoder Original Position is", self.ENCODER_ORIGINAL_POSITION)

        # Decode Message received after writing Multi turn data as a Zero Position to ROM 0x63
        # Decode Read Multi_turn Encoder Zero Offset Message 0x62
        # Decode Message received after writing current Multi turn data as a Zero Position to ROM 0x64
        elif (
            Message.data[0] == 0x62
            or Message.data[0] == 0x63
            or Message.data[0] == 0x64
        ):
            self.ENCODER_OFFSET_POSITION = Signed_hex_to_int(
                (f"{Array[7]}{Array[6]}{Array[5]}{Array[4]}"), 32
            )
            print("ENCODER_OFFSET_POSITION is", self.ENCODER_OFFSET_POSITION)

        # Decode the Multi Turn Angle Reply 0x92
        elif Message.data[0] == 0x92:
            self.MULTI_TURN_ANG_OUT = (
                Signed_hex_to_int((f"{Array[7]}{Array[6]}{Array[5]}{Array[4]}"), 32)
            ) / 100
            self.MULTI_TURN_REV_OUT = self.MULTI_TURN_ANG_OUT / 360
            # print('No of Turns of external Shaft =', self.MULTI_TURN_ANG_OUT, 'deg or', self.MULTI_TURN_REV_OUT, 'rotations')

        # Decode The Message Received from Motor Status 1 0x9A
        elif Message.data[0] == 0x9A:
            # Temperature Calculation
            self.TEMPERATURE = Signed_hex_to_int(Array[1], 8)
            print("Temperature is", self.TEMPERATURE)
            # Break_status 0=Lock & 1=Released
            self.Brake_status = int(Array[3], 16)
            print("Break Status(0=Lock & 1=Released) is", self.Brake_status)
            # Voltage Calculaion
            self.VOLTAGE = int((f"{Array[5]}{Array[4]}"), 16) * 0.1
            print("Voltage is", self.VOLTAGE)
            # Error Status
            Error_dict = {
                0: "No Error",
                2: "Motor Stall",
                4: "low Pressure",
                8: "Over Voltage",
                16: "Over Current",
                64: "Power Overrun",
                256: "Speeding",
                4096: "Over Temperature",
                8192: "Encoder Calibration Error",
            }
            self.ERROR_STATUS = Error_dict[int((f"{Array[7]}{Array[6]}"), 16)]
            print("Error Status is", self.ERROR_STATUS)

        # Decode The Message Received from Motor Status 3 0x9D
        elif Message.data[0] == 0x9D:
            # Temperature Calculation
            self.TEMPERATURE = Signed_hex_to_int(Array[1], 8)
            print("Temperature is", self.TEMPERATURE)
            # Phase A Current Calculaion
            self.PHASE_A_CURRENT = (
                Signed_hex_to_int((f"{Array[3]}{Array[2]}"), 16) * 0.01
            )
            print("A Current is", self.PHASE_A_CURRENT)
            # Phase B Current Calculaion
            self.PHASE_B_CURRENT = (
                Signed_hex_to_int((f"{Array[5]}{Array[4]}"), 16) * 0.01
            )
            print("B Current is", self.PHASE_B_CURRENT)
            # Phase C Current Calculaion
            self.PHASE_C_CURRENT = (
                Signed_hex_to_int((f"{Array[7]}{Array[6]}"), 16) * 0.01
            )
            print("C Current is", self.PHASE_C_CURRENT)

        # Decode Motor Shutdown Reply 0x80
        elif Message.data[0] == 0x80:
            print("Motor Shutdowned")

        # Decode Motor Stop Reply 0x81
        elif Message.data[0] == 0x81:
            print("Motor Stopped")

        # Decode System Operate read reply 0x70
        elif Message.data[0] == 0x70:
            Mode_dict = {
                0: "Standby",
                1: "Torque Mode",
                2: "Speed Mode",
                3: "Position Mode",
            }
            self.MOTOR_MODE = Mode_dict[int((f"{Array[7]}"), 16)]
            print("Motor is Running in", self.MOTOR_MODE)

        # Decode Power Read Replay 0x71
        elif Message.data[0] == 0x71:
            self.POWER = int((f"{Array[7]}{Array[6]}"), 16) * 0.1
            print("Power is", self.POWER)

        # Decode System Reset Reply 0x76
        elif Message.data[0] == 0x76:
            print("System is Resetted")

        # Decode Brake Release Reply 0x77
        elif Message.data[0] == 0x77:
            print("Motor Brake is Released")

        # Decode Apply Brake Reply 0x78
        elif Message.data[0] == 0x78:
            print("Motor Brake is Applied")

        # Decode System runtime (ms) reply 0xB1
        elif Message.data[0] == 0xB1:
            self.RUNTIME = int((f"{Array[7]}{Array[6]}{Array[5]}{Array[4]}"), 16)
            print("System Runtime(ms) is", self.RUNTIME)

        # Decode System Version Date 0xB2
        elif Message.data[0] == 0xB2:
            self.Version_Date = int((f"{Array[7]}{Array[6]}{Array[5]}{Array[4]}"), 16)
            print("System Version Date(yyyymmdd) is", self.Version_Date)

        # Decode Communication Interruption time(ms)(0=Disable) 0xB3
        elif Message.data[0] == 0xB3:
            self.Comm_Interrupt_time = int(
                (f"{Array[7]}{Array[6]}{Array[5]}{Array[4]}"), 16
            )
            print("Communication Interruption Time in ms is", self.Comm_Interrupt_time)

        # Decode The Message Received from Motor Status 3 0x9C
        # Decode Torque command Reply 0xA1
        # Decode Speed command Reply 0xA2
        # Decode Absolute Position command Reply 0xA4
        # Decode Incremental Position command Reply 0xA8
        elif (
            Message.data[0] == 0xA1
            or Message.data[0] == 0xA2
            or Message.data[0] == 0xA4
            or Message.data[0] == 0xA8
            or Message.data[0] == 0x9C
        ):
            # if Message.data[0] == 0x9C:
            #     print('Read Motor Status 2')
            # elif Message.data[0] ==0xA1:
            #     print("Torque control Mode")
            # elif Message.data[0] ==0xA2:
            #     print("Speed control Mode")
            # elif Message.data[0] ==0xA4:
            #     print("Absolute Position control Mode")
            # elif Message.data[0] ==0xA8:
            #     print("Incremental Position control Mode")
            # Temperature Calculation
            self.TEMPERATURE = Signed_hex_to_int(Array[1], 8)
            # print("Temperature is",self.TEMPERATURE)
            # Torque Current Calculation
            self.TORQUE_CURRENT = (
                Signed_hex_to_int((f"{Array[3]}{Array[2]}"), 16)
            ) * 0.01
            # print('Torque Current is',self.TORQUE_CURRENT)
            # Speed Calculation
            self.SPEED_OUT_DPS = Signed_hex_to_int((f"{Array[5]}{Array[4]}"), 16)
            self.SPEED_OUT_RPS = self.SPEED_OUT_DPS / 360
            # print('Speed is', self.SPEED_OUT_DPS, 'dps', 'or', self.SPEED_OUT_RPS, 'rps')
            # Encoder Position Calculation
            self.ENCODER_POSITION = Signed_hex_to_int((f"{Array[7]}{Array[6]}"), 16)
            # print('Encoder is at position', self.ENCODER_POSITION)

        # Read and Write ID 0x79
        elif Message.data[0] == 0x79:
            if Message.data[2] == 0x00:
                Motor_ID = int((f"{Array[7]}"), 16)
                print("Wrote Motor ID for ", Motor_ID)
            elif Message.data[2] == 0x01:
                Motor_ID = int((f"{Array[7]}{Array[6]}"), 16) - 0x240
                print("Connected Motor ID is ", Motor_ID)

        else:
            print("Mesg Not Decoded")
