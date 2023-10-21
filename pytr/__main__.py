#!/usr/bin/env python3
import logging
import sys

from pytr.main import main

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log = logging.getLogger(__name__)
        log.warning("Interrupt from keyboard (CTRL + C).")
        sys.exit()
    except Exception as e:
        log = logging.getLogger(__name__)
        log.critical("The program is terminated due to an unhandled exception.")
        raise
