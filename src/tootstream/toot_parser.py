import emoji
from colored import attr
from html.parser import HTMLParser
from textwrap import TextWrapper


def unique(sequence):
    seen = set()
    return [x for x in sequence if not (x in seen or seen.add(x))]


def emoji_shortcode_to_unicode(text):
    """Convert standard emoji short codes to unicode emoji in
    the provided text.

      text - The text to parse.
      Returns the modified text.
    """
    return emoji.emojize(text, use_aliases=True)


def emoji_unicode_to_shortcodes(text):
    """Convert unicode emoji to standard emoji short codes."""
    return emoji.demojize(text)


def find_attr(name, attrs):
    """Find an attribute in an HTML tag by name.

      name - The attribute name to search for.
      attrs - The list of attributes to search.
      Returns the matching attribute or None.
    """
    for attr, values in attrs:
        if attr == name:
            return values
    return None


def has_class(value, attrs):
    """Return whether the HTML attributes contain a specific class name.

      value - The class type to search for.
      attrs - The list of attributes to search.
      Returns true if the specified class type was found.
    """
    values = find_attr('class', attrs)
    if values is None:
        return False

    return values.find(value) >= 0


class TootParser(HTMLParser):
    """
    TootParser is used to parse HTML based toots and convert them into
    plain text versions.  By default the returned text is equivalent to the
    source toot text with paragraph and br tags converted to line breaks.

    The text can optionally be indented by passing a string to the indent
    field which is prepended to every line in the source text.

    The text can also have text wrapping enabled by passing in a max width to
    the width parameter.  Note that the text wrapping is not perfect right
    now and doesn't work well with terminal colors and a lot of unicode text
    on one line.

    Link shortening can be enabled by setting the shorten_links parameter.
    This shortens links by using the link shortening helper HTML embedded in
    the source toot.  This means links embedded from sources other than
    mastodon may not be shortened.  The shortened urls will look like
    example.org/areallylongur...

    Emoji short codes can optionally be converted into unicode based emoji by
    enabling the convert_emoji parameter.  This parses standard emoji short
    code names and does not support custom emojo short codes.

    Styles can also optionally be applied to links found in the source text.
    Pass in the desired colored style to the link_style, mention_style, and
    hashtag_style parameters.

    To parse a toot, pass the toot source HTML to the parse() command. The
    source text can then be retrieved with the get_text() command.  Parsed
    link urls can also be retrieved by calling the get_links() command.

      indent - A string to prepend to all lines in the output text.
      width - The maximum number of characters to allow in a line of text.
      shorten_links - Whether or not to shorten links.
      convert_emoji_to_unicode - Whether or not to convert emoji short codes to unicode.
      convert_emoji_to_shortcode - Whether or not to convert emoji unicode to short codes unicode.
      link_style - The colored style to apply to generic links.
      mention_style - The colored style to apply to mentions.
      hashtag_style - The colored style to apply to hashtags.

    """

    def __init__(
            self,
            indent='',
            width=0,
            convert_emoji_to_unicode=False,
            convert_emoji_to_shortcode=False,
            shorten_links=False,
            link_style=None,
            mention_style=None,
            hashtag_style=None):

        super().__init__()
        self.reset()
        self.strict = False
        self.convert_charrefs = True

        self.indent = indent
        self.convert_emoji_to_unicode = convert_emoji_to_unicode
        self.convert_emoji_to_shortcode = convert_emoji_to_shortcode
        self.shorten_links = shorten_links
        self.link_style = link_style
        self.mention_style = mention_style
        self.hashtag_style = hashtag_style

        if width > 0:
            self.wrap = TextWrapper()
            self.wrap.initial_indent = indent
            self.wrap.subsequent_indent = indent
            self.wrap.width = width
        else:
            self.wrap = None


    def reset(self):
        """Resets the parser so a new toot can be parsed."""
        super().reset()
        self.fed = []
        self.lines = []
        self.links = []
        self.weblinks = []
        self.cur_type = None
        self.hide = False
        self.ellipsis = False


    def pop_line(self):
        """Take the current text scratchpad and return it as a
        line of text and reset the scratchpad."""
        line = ''.join(self.fed)
        self.fed = []
        return line


    def handle_data(self, data):
        """Processes plain text data.
          data - The text to process
        """
        if self.hide:
            return

        if self.convert_emoji_to_unicode:
            data = emoji_shortcode_to_unicode(data)

        if self.convert_emoji_to_shortcode:
            data = emoji_unicode_to_shortcodes(data)

        self.fed.append(data)


    def parse_link(self, attrs):
        """Processes a link tag.
          attrs - A list of attributes contained in the link tag.
        """

        # Save the link url
        self.links.append(find_attr('href', attrs))

        if has_class('hashtag', attrs):
            self.cur_type = 'hashtag'
            if self.hashtag_style != None:
                self.fed.append(self.hashtag_style)
        elif has_class('mention', attrs):
            self.cur_type = 'mention'
            if self.mention_style != None:
                self.fed.append(self.mention_style)
        else:
            self.weblinks.append(find_attr('href', attrs))
            self.cur_type = 'link'
            if self.link_style != None:
                self.fed.append(self.link_style)


    def parse_span(self, attrs):
        """Processes a span tag.
          attrs - A list of attributes contained in the span tag.
        """

        # Right now we only support spans used to shorten links.
        # Mastodon links contain <span class="hidden"> tags around
        # text that should be omitted in the shorted link version
        # and <span class="ellipsis"> tags around text that should
        # be terminated with an ellipsis.
        if not self.shorten_links or self.cur_type != 'link':
            return

        if has_class('invisible', attrs):
            # Mark that any text in the tag should be omitted
            self.hide = True

        elif has_class('ellipsis', attrs):
            # Mark the any text in the tag should be terminated
            # with ellipsis
            self.ellipsis = True


    def handle_starttag(self, tag, attrs):
        """Parses a new HTML tag.
          tag - The name of the new tag.
          attrs - The attributes contained in the tag.
        """
        if tag == 'a':
            self.parse_link(attrs)

        elif tag == 'span':
            self.parse_span(attrs)

        elif tag == 'br':
            self.lines.append(self.pop_line())

        elif tag == 'p' and len(self.fed) > 0:
            self.lines.append(self.pop_line())
            self.lines.append('')


    def handle_endtag(self, tag):
        """Parses a closing tag.
          tag - The tag to parse.
        """
        if tag == 'a':
            # Reset if we are applying a style
            if ((self.cur_type == 'link' and self.link_style != None) or
                (self.cur_type == 'mention' and self.mention_style != None) or
                (self.cur_type == 'hashtag' and self.hashtag_style != None)):
                self.fed.append(attr('reset'))

            # Only types associated with 'a' tags are tracked at the moment
            self.cur_type = None

        if tag == 'span' and self.hide:
            # Allow text to be shown now that the hide span
            # has finished
            self.hide = False

        if tag == 'span' and self.ellipsis:
            # Add ellipsis to the text if we have finished a
            # <span class="ellipsis"> tag.
            self.fed.append('...')
            self.ellipsis = False


    def parse(self, html):
        """Parses a single source toot.
          html - The source HTML of the toot.
        """
        self.reset()
        self.feed(html)
        self.close()


    def get_text(self):
        """Returns a plain text version of the source HTML toot."""

        # Add the last line from the scratchpad.
        self.lines.append(self.pop_line())

        if self.wrap == None:
            return self.indent + ('\n' + self.indent).join(self.lines)

        # Text wrap the lines by feeding them to TextWrapper first.
        out = []
        for line in self.lines:
            if len(line) == 0:
                out.append(line)
            else:
                out.append(self.wrap.fill(line))
        return '\n'.join(out)

    def get_links(self):
        """Returns an array of links parsed from the source HTML toot."""
        return self.links

    def get_weblinks(self):
        """Returns an array of non-mastodon links parsed from the toot."""
        links = self.weblinks
        links.extend(self.get_links())
        links = unique(links)
        return links
