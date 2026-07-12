#!/usr/bin/env python3

from zlac8015d import ZLAC8015D
import time

PORT = "/dev/ttyACM0"


def print_faults(motor):
    try:
        left_fault, right_fault = motor.get_fault_code()

        print("\n========== FAULT STATUS ==========")
        print(f"LEFT : {left_fault}")
        print(f"RIGHT: {right_fault}")
        print("==================================\n")

    except Exception as e:
        print("Failed to read fault:", e)


def main():

    motor = ZLAC8015D.Controller(port=PORT)

    print("\nConnected to", PORT)

    try:
        print("Disabling motor...")
        motor.disable_motor()
        time.sleep(1)

        print("Reading initial faults...")
        print_faults(motor)

        print("Clearing alarms...")
        motor.clear_alarm()
        time.sleep(1)

        print("Faults after clear:")
        print_faults(motor)

        print("Setting velocity mode...")
        motor.set_mode(3)

        time.sleep(0.5)

        try:
            mode = motor.get_mode()
            print("Current mode:", mode)
        except Exception as e:
            print("Could not read mode:", e)

        print("Setting accel/decel...")
        motor.set_accel_time(1000, 1000)
        motor.set_decel_time(1000, 1000)

        print("Enabling motor...")
        motor.enable_motor()

        time.sleep(1)

        print("Faults after enable:")
        print_faults(motor)

        print("\nCommanding LEFT motor only at 100 RPM")
        print("RIGHT motor = 0 RPM\n")

        motor.set_rpm(100, 0)

        while True:

            try:
                rpm_l, rpm_r = motor.get_rpm()

                try:
                    tick_l, tick_r = motor.get_wheels_tick()
                except:
                    tick_l = tick_r = -1

                try:
                    lf, rf = motor.get_fault_code()
                except:
                    lf = rf = "N/A"

                print(
                    f"RPM L={rpm_l:7.1f} "
                    f"RPM R={rpm_r:7.1f} | "
                    f"Tick L={tick_l:10d} "
                    f"Tick R={tick_r:10d} | "
                    f"Fault L={lf} "
                    f"Fault R={rf}"
                )

                time.sleep(0.5)

            except KeyboardInterrupt:
                break

    finally:
        print("\nStopping motor...")
        try:
            motor.set_rpm(0, 0)
            time.sleep(1)
            motor.disable_motor()
        except:
            pass

        print("Done.")


if __name__ == "__main__":
    main()
