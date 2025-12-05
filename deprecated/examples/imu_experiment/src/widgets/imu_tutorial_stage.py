from PyQt6.QtCore import pyqtSignal

from natKit.client.gui.pyqt6.widget import Stage, StageBuilder, ExperimentBuilder
from natKit.common.kafka import KafkaManager


class ImuTutorialStage():
    onNext = pyqtSignal()
    onPrev = pyqtSignal()

    def __init__(self, kafka_manager: KafkaManager, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.kafka_manager = kafka_manager
        self.stage = StageBuilder().set_name("Tutorial Stage").set_prompt("This is the tutorial").build()
        self.stage.run()
