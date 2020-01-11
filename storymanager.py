import json
import re
from getconfig import settings
from utils import output, format_result, get_similarity


class Story:
    # the initial prompt is very special.
    # We want it to be permanently in the AI's limited memory (as well as possibly other strings of text.)
    def __init__(self, generator, context='', memory=None):
        if memory is None:
            memory = []
        self.generator = generator
        self.context = context
        self.memory = memory
        self.actions = []
        self.results = []
        self.savefile = ""

    def act(self, action, record=True, format=True):
        assert (self.context.strip() + action.strip())
        assert (settings.getint('top-keks') is not None)
        result = self.generator.generate(
            self.get_story() + action,
            self.context + ' '.join(self.memory),
            temperature=settings.getfloat('temp'),
            top_p=settings.getfloat('top-p'),
            top_k=settings.getint('top-keks'),
            repetition_penalty=settings.getfloat('rep-pen'))
        if format:
            action = format_result(action)
            result = format_result(result)
        if record:
            self.actions.append(action)
            self.results.append(result)
        return result

    def print_action_result(self, i, wrap=True, color=True):
        col1 = 'user-text' if color else None
        col2 = 'ai-text' if color else None
        if i == 0 or len(self.actions) == 1:
            start = self.context + ' ' + self.actions[0]
            result = self.results[0]
            is_start_end = re.match(r"[.!?]\s*$", start)
            is_result_beg = re.match(r"^\s*[a-z.!?,\"]", result)
            sep = ' ' if not is_start_end and is_result_beg else '\n'
            output(self.context + self.actions[0], col1, self.results[0], col2, sep=sep)
        else:
            if i < len(self.actions) and self.actions[i].strip() != "":
                caret = "> " if re.match(r"^ *you +", self.actions[i], flags=re.I) else ""
                output(caret + self.actions[i], col1, wrap=wrap)
            if i < len(self.results) and self.results[i].strip() != "":
                output(self.results[i], col2, wrap=wrap)

    def print_story(self, wrap=True, color=True):
        for i in range(0, max(len(self.actions), len(self.results))):
            self.print_action_result(i, wrap=wrap, color=color)

    def print_last(self, wrap=True, color=True):
        self.print_action_result(-1, wrap=wrap, color=color)

    def get_story(self):
        lines = [val for pair in zip(self.actions, self.results) for val in pair]
        return '\n\n'.join(lines)

    def revert(self):
        self.actions = self.actions[:-1]
        self.results = self.results[:-1]

    def get_suggestion(self):
        return re.sub('\n.*', '',
                      self.generator.generate_raw(
                          self.get_story() + "\n\n> You",
                          self.context,
                          temperature=settings.getfloat('action-temp'),
                          top_p=settings.getfloat('top-p'),
                          top_k=settings.getint('top-keks'),
                          repetition_penalty=1))

    def __str__(self):
        return self.context + ' ' + self.get_story()

    def to_dict(self):
        res = {}
        res["temp"] = settings.getfloat('temp')
        res["top-p"] = settings.getfloat("top-p")
        res["top-keks"] = settings.getint("top-keks")
        res["rep-pen"] = settings.getfloat("rep-pen")
        res["context"] = self.context
        res["memory"] = self.memory
        res["actions"] = self.actions
        res["results"] = self.results
        return res

    def from_dict(self, d):
        settings["temp"] = str(d["temp"])
        settings["top-p"] = str(d["top-p"])
        settings["top-keks"] = str(d["top-keks"])
        settings["rep-pen"] = str(d["rep-pen"])
        self.context = d["context"]
        self.memory = d["memory"]
        self.actions = d["actions"]
        self.results = d["results"]

    def to_json(self):
        return json.dumps(self.to_dict())

    def from_json(self, j):
        self.from_dict(json.loads(j))

    def is_looping(self, threshold=0.9):
        if len(self.results) >= 2:
            similarity = get_similarity(self.results[-1], self.results[-2])
            if similarity > threshold:
                return True
        return False

#    def save()
#        file=Path('saves', self.filename)
