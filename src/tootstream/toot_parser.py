from html.parser import HTMLParser
from textwrap import TextWrapper

class TootParser(HTMLParser):
    def __init__(self,
            indent = '',
            width = 0):

        super().__init__()
        self.reset()
        self.strict = False
        self.convert_charrefs = True

        self.indent = indent

        if width > 0:
            self.wrap = TextWrapper()
            self.wrap.initial_indent = indent
            self.wrap.subsequent_indent = indent
            self.wrap.width = width
        else:
            self.wrap = None

    def reset(self):
        super().reset()
        self.fed = []
        self.lines = []
        self.cur_type = None

    def pop_line(self):
        line = ''.join(self.fed)
        self.fed = []
        return line

    def handle_data(self, data):
        self.fed.append(data)

    def handle_starttag(self, tag, attrs):
        if tag == 'br':
            self.lines.append(self.pop_line())
        if tag == 'p' and len(self.fed) > 0:
            self.lines.append(self.pop_line())
            self.lines.append('')

    def get_text(self):
        self.lines.append(self.pop_line())

        if self.wrap == None:
            return self.indent + ('\n' + self.indent).join(self.lines)

        out = []
        for line in self.lines:
            if len(line) == 0:
                out.append(line)
            else:
                out.append(self.wrap.fill(line))

        return '\n'.join(out)
