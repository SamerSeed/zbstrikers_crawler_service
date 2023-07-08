from dataclasses import dataclass, field
from typing import List
import ahocorasick
import pickle

class WordSearchWrapper:
    def __init__(self, words:List[str], assemble:bool=True)->None:
        self.automaton = ahocorasick.Automaton()
        for idx, word in enumerate(words):
            self.automaton.add_word(word, (idx, word))
        if assemble:
            self.automaton.make_automaton()
    def check_text(self, text:str)->bool:
        return len(list(self.automaton.iter(text))) > 0
    def dump(self, path:str)->None:
        self.automaton.dump(path, pickle.dumps)
    @staticmethod
    def from_pickle(path:str):
        res = WordSearchWrapper([], assemble=False)
        res.automaton.load(path, pickle.loads)
        return res

    
if __name__=="__main__":
    wswrper = WordSearchWrapper(["два", "пятнадцать", "нет"])
    assert wswrper.check_text("grkenog нет ")
    assert not wswrper.check_text("gjvngnrvoin мташтмт ")
    assert not wswrper.check_text("")
    