import logging
import os

# Ensure the logs directory exists (optional, but good practice if we put it in a subdir)
# For now, we'll just put it in the root or a standard location.
# Let's write to "hidden_state.log" in the current working directory.

def setup_hidden_logger(name="hidden_state", log_file="hidden_state.log"):
    """
    Sets up a logger that writes only to a file.
    """
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)

    # Check if handler already exists to avoid duplicate logs
    if not logger.handlers:
        file_handler = logging.FileHandler(log_file)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(message)s')
        file_handler.setFormatter(formatter)

        logger.addHandler(file_handler)

        # Prevent propagation to the root logger to avoid printing to stdout
        logger.propagate = False

    return logger

# Singleton-like access
hidden_logger = setup_hidden_logger()
