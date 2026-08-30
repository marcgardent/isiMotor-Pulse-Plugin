"""
isiMotor-RawUDP-Manager main application entry point.
"""

from .ui.app import IsiMotorBenchmarkApp, main

__all__ = ["IsiMotorBenchmarkApp", "main"]

if __name__ == "__main__":
    main()
