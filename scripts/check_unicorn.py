"""Check whether the Unicorn Hybrid Black SDK and headset are available."""

from mindbridge_chess.eeg_acquisition import EEGAcquisition


def main() -> None:
    print("Unicorn Hybrid Black preflight")
    print("------------------------------")

    if not EEGAcquisition.unicorn_sdk_available():
        print("SDK: NOT FOUND")
        print("Install the vendor UnicornPy SDK from g.tec/Unicorn before hardware testing.")
        return

    print("SDK: found")
    devices = EEGAcquisition.available_devices()
    if not devices:
        print("Devices: none found")
        print("Pair/connect the headset, then rerun this script.")
        return

    print(f"Devices: {len(devices)} found")
    for idx, device in enumerate(devices):
        print(f"  [{idx}] {device}")

    eeg = EEGAcquisition({"allow_simulation": False})
    try:
        eeg.start()
        print(f"Streaming: OK ({eeg.status.device_name})")
    finally:
        eeg.stop()


if __name__ == "__main__":
    main()
