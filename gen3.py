import re

class MermaidParser:
    def __init__(self, file_path):
        self.file_path = file_path
        self.blocks = {}
        self.logic = []

    def parse(self):
        mermaid_comment = '%%'
        loop_pattern_single = re.compile(r'^subgraph\s*(\w+)\s*\[(.+)\]$')
        loop_pattern_begin = re.compile(r'^subgraph\s*(\w+)\s*\[(.*)$')
        block_pattern_begin = re.compile(r'^(\w+)\s*\[(.*)$')
        block_pattern_single = re.compile(r'^(\w+)\s*\[(.+)\]$')
        logic_pattern = re.compile(r'^(\w+)\s*-->\s*(\|\w+\|)?\s*(\w+)$')
        with open(self.file_path, 'r') as file:
            lines = file.readlines()

        self.current_block_id = None
        self.current_block_lines = []
        in_block = False
        in_loop = False

        for line in lines:
            line = line.strip()
            if self.ignore_comments(line):
                continue

            if self.get_single_line_block(line):
                continue

            # Single-line loop block
            if self.get_single_loop_block(line):
                in_loop = True
                continue

            # Start Loop block
            if not in_loop:
                if self.start_loop_block(line):
                    in_loop = True
                    in_block = True
                    continue

            # Multiline loop block continuation
            if in_loop and in_block:
                if self.end_of_line(line):
                    self.block_join(line)
                    in_block = False
                else:
                    self.block_append(line)
                continue

            # Loop block contents
            if in_loop:
                if self.end_of_loop(line):
                    self.block_join(line)
                    in_loop = False
                else:
                    self.block_append(line)
                continue


            # Start of a multiline block
            if not in_block:
                if self.start_multi_block(line):
                    in_block = True
                    continue

            # Multiline continuation
            if in_block:
                if self.end_of_line(line):
                    self.block_join(line)
                    in_block = False
                else:
                    self.block_append(line)
                continue

            # Logic connections
            self.match_logic(line)

    def start_loop_block(self, line):
        """
        """
        loop_pattern_begin = re.compile(r'^subgraph\s*(\w+)\s*\[(.*)$')
        return self.match_block(line, loop_pattern_begin)

    def start_multi_block(self, line):
        """
        """
        block_pattern_begin = re.compile(r'^(\w+)\s*\[(.*)$')
        return self.match_block(line, block_pattern_begin)

    def match_block(self, line, pattern):
        """
        """
        start_match = pattern.match(line)
        if start_match and not line.endswith(']'):
            self.current_block_id, first_line = start_match.groups()
            self.current_block_lines = [first_line]
            return True

    def end_of_loop(self, line):
        """
        """
        if line.startswith('end'):
            return True
        else:
            return False

    def get_single_loop_block(self, line):
        loop_pattern_single = re.compile(r'^subgraph\s*(\w+)\s*\[(.+)\]$')
        match = loop_pattern_single.match(line)
        if match:
            block_id, content = match.groups()
            self.current_block_id = block_id
            self.current_block_lines = [content]
            return True

    def end_of_line(self, line):
        """
           Checks for end of line
        """
        if line.endswith(']'):
            return True
        else:
            return False

    def block_join(self, line):
        """
        """
        self.current_block_lines.append(line[:-1])
        self.blocks[self.current_block_id] = "\n".join(self.current_block_lines).strip()
        return

    def block_append(self, line):
        self.current_block_lines.append(line)
        return

    def match_logic(self, line):
        """
            Parses line to get any logic information 
            e.g:
            key1 --> key2
            key1 --> |key3| key2
        """
        logic_pattern = re.compile(r'^(\w+)\s*-->\s*(\|\w+\|)?\s*(\w+)$')
        logic_match = logic_pattern.match(line)
        if logic_match:
            if logic_match.lastindex == 3: # Has 3 information
                self.logic.append((logic_match.group(1),
                    logic_match.group(3),logic_match.group(2)))
            else:
                self.logic.append((logic_match.group(1), logic_match.group(2)))


    def ignore_comments(self, line):
        """
            Parses line and remove comments, empty line or flowchart keyword
        """
        mermaid_comment = '%%'
        if not line or line.startswith("flowchart") or \
        line.startswith(mermaid_comment):
            return True
        else:
            return False

    def get_single_line_block(self, line):
        """  Parses line  and looks for single line block
            block_id [ content ]
        """
        block_pattern_single = re.compile(r'^(\w+)\s*\[(.+)\]$')
        match = block_pattern_single.match(line)
        if match:
            block_id, content = match.groups()
            self.blocks[block_id] = content.strip()
            return True
        else:
            return False

    def get_blocks(self):
        return self.blocks

    def get_logic(self):
        return self.logic

class ControlBlock(MermaidParser):
    def __init__(self):
        pass
