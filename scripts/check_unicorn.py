"""Check whether the Unicorn Hybrid Black SDK and headset are available."""

from mindbridge_chess.eeg_acquisition import EEGAcquisition


def _print_lsl_streams() -> None:
    try:
        from pylsl import resolve_streams
    except Exception as exc:
        print(f"LSL: unavailable ({exc})")
        return

    streams = [
        stream
        for stream in resolve_streams(wait_time=3.0)
        if stream.type().lower() == "eeg" and "unicorn" in stream.name().lower()
    ]
    if not streams:
        print("LSL: no Unicorn EEG streams found")
        return

    print(f"LSL: {len(streams)} Unicorn EEG stream(s) found")
    for stream in streams:
        print(
            f"  {stream.name()} "
            f"({stream.channel_count()} ch, {stream.nominal_srate()} Hz)"
        )


def main() -> None:
    print("Unicorn Hybrid Black preflight")
    print("------------------------------")

    if not EEGAcquisition.unicorn_sdk_available():
        print("SDK: NOT FOUND")
        _print_lsl_streams()
    else:
        print("SDK: found")
        devices = EEGAcquisition.available_devices()
        if not devices:
            print("SDK devices: none found")
        else:
            print(f"SDK devices: {len(devices)} found")
            for idx, device in enumerate(devices):
                print(f"  [{idx}] {device}")

    eeg = EEGAcquisition({"allow_simulation": False})
    try:
        eeg.start()
        print(f"Streaming: OK ({eeg.status.mode}, {eeg.status.device_name})")
    finally:
        eeg.stop()


if __name__ == "__main__":
    main()
