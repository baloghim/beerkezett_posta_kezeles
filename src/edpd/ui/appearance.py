from PySide2.QtWidgets import QApplication, QStyleFactory


def apply_style(name):
    """Use an available native Qt style, with Fusion as the safe default."""
    keys = QStyleFactory.keys()
    selected = next((key for key in keys if key.lower() == name.lower()), None)
    selected = selected or next((key for key in keys if key.lower() == 'fusion'), None)
    if selected:
        QApplication.instance().setStyle(QStyleFactory.create(selected))
    return QApplication.instance().style().objectName()
