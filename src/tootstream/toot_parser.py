from html.parser import HTMLParser
from textwrap import TextWrapper
from colored import fg, attr, stylize

def extract_mention_url(attrs):
    """
    Takes a list of (key, value) attribute pairs like the one given in
    HTMLParser for an <a> tag, and determine whether this <a> tag is a mention.
    If so, return the href value, which is the URL of the user's profile;
    otherwise return None.
    """
    is_mention = False
    href = None
    for key, value in attrs:
        if key == 'class' and 'mention' in value.split():
            is_mention = True
        elif key == 'href':
            href = value
    if is_mention:
        return href
    else:
        return None

class TootParser(HTMLParser):
    def __init__(self,
            indent = '',
            width = 0):

        super().__init__()
        self.reset()
        self.base_style = attr('reset')
        self.strict = False
        self.convert_charrefs = True

        # We'll decide how to format mentions based on the tag attributes
        # alone, so we set this flag to remember to ignore the text encountered
        # inside the tag.
        self.in_mention = False

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

    def set_mentions(self, mentions):
        self.mentions = dict()
        if mentions:
            for mention in mentions:
                url = mention.get('url')
                if url is not None:
                    self.mentions[url] = mention

    def get_text_for_mention(self, mention):
        """
        Given a mention dict as provided by mastodon.py, format it as text.
        Returns None if the mention does not exist or does not contain an
        account for some reason.
        """

        if mention is None: return None
        acct = mention.get('acct')
        if acct is None: return None
        acct_text = fg('green') + '@' + acct + self.base_style
        id_text = fg('red') + '(id:{})'.format(mention.get('id', '?')) + self.base_style
        return acct_text + ' ' + id_text

    def pop_line(self):
        line = ''.join(self.fed)
        self.fed = []
        return line

    def handle_data(self, data):
        if not self.in_mention:
            self.fed.append(data)

    def handle_starttag(self, tag, attrs):
        if tag == 'br':
            self.lines.append(self.pop_line())
        elif tag == 'p' and len(self.fed) > 0:
            self.lines.append(self.pop_line())
            self.lines.append('')
        elif tag == 'a':
            mentioned_href = extract_mention_url(attrs)
            if mentioned_href is not None:
                mention = self.mentions.get(mentioned_href, dict())
                text = self.get_text_for_mention(mention)
                if text is not None:
                    self.fed.append(text)
                    self.in_mention = True

    def handle_endtag(self, tag):
        if tag == 'a':
            self.in_mention = False

    def get_text(self):
        self.lines.append(self.pop_line())

        if self.wrap == None:
            return self.indent + self.base_style + ('\n' + self.indent).join(self.lines)

        out = []
        for line in self.lines:
            if len(line) == 0:
                out.append(line)
            else:
                out.append(self.wrap.fill(line))

        return self.base_style + '\n'.join(out)
