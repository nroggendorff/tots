import sys

from PyQt5.QtWidgets import QApplication
from gui.main_window import DotDrawerApp


def main():
    app = QApplication(sys.argv)
    win = DotDrawerApp()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
