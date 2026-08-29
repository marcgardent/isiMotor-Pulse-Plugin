"""
isiMotor-RawUDP-Manager main application entry point.
"""

from .sniffer import IsiMotorBenchmarkApp, main

__all__ = ["IsiMotorBenchmarkApp", "main"]

if __name__ == "__main__":
    main()
