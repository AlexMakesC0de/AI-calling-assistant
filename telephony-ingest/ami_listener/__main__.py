"""Entry point for the AMI CDR listener."""

import logging

from ami_listener.listener import run

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)

if __name__ == "__main__":
    run()
