import re

freq_multiplier_units = {'mhz' : 1000000,
                         'khz' : 1000,
                         'hz'  : 1}

time_multiplier_units = {'ms' : 1000000,
                         'us' : 1000,
                         'ns' : 1}

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

class Block(MermaidParser):
    def __init__(self, block_id, content):
        self.block_id = block_id
        self.content = content

    def get_cols(self, line):
        delimiter = ",| |\t"
        line = line.lower()
        return list(filter(None, re.split(delimiter,line)))

    def chan_on(self, chan_string):
        chan_list = []
        comment = ""
        for part in self.get_cols(chan_string):
            if self.is_comment(part):
                comment = part[1:]
            elif '-' in part:
                start, end = map(int, part.split('-'))
                chan_list.extend(range(start, end + 1))
            else:
                chan_list.append(int(part))
        return list(set(chan_list)), comment # remove duplicate

    def split_unit(self, string):
        return re.findall(r'\d+|\D+', string)

    def parse_contents(self):
        return self.content.split('\n')

    def is_comment(self, line):
        if line.strip().startswith("#"):
            return True
        else:
            return False

    def eat_space_between_units(self, l):
        t = [x in time_multiplier_units for x in l]
        f = [x in freq_multiplier_units for x in l]
        for i, x in enumerate(t):
            if x:
                l[i-1] += l[i]
                l.pop(i)

        for i, x in enumerate(f):
            if x:
                l[i-1] += l[i]
                l.pop(i)

        return l

class ControlBlock(Block):
    def __init__(self, block_id, content):
        super().__init__(block_id, content)
        self.block_type = "control"
        self.clockselect = {'auto': 0, 'external':1, 'internal':2,'direct':3}
        self.dacselect = {'static': 0, 'single':1, 'half':2,'full':3}
        self.control_grammar = ["clock", "evars", "ivars", "auxout",
                "dacconfig", "version"]

    def process_control(self):
        for line in self.parse_contents():
            cols = self.get_cols(line)
            first_col = cols[0]
            next_cols = cols[1:]
            assert first_col in self.control_grammar, f"{first_col} doesn't match syntax"
            """ # To migrate to python3.10 syntax
            match first_col:
                case "clock":
                    ...
                case "evars":
                    ...
            """
            if first_col == self.control_grammar[0]:
                self.set_clock(next_cols)
            elif first_col == self.control_grammar[1]:
                self.set_evars(next_cols)
            elif first_col == self.control_grammar[2]:
                self.set_ivars(next_cols)
            elif first_col == self.control_grammar[3]:
                self.set_auxline_polarity(next_cols)
            elif first_col == self.control_grammar[4]:
                self.set_DACconfig(next_cols)
            elif first_col == self.control_grammar[5]:
                self.set_patgenversion(next_cols)

    def set_clock(self, clock_cols):
        clock_cols = self.eat_space_between_units(clock_cols)
        for i, part in enumerate(clock_cols):
            if i == 0: # Clock value and unit
                value, unit = self.split_unit(part)
                assert unit in freq_multiplier_units.keys(), "Undefined frequency units.(Hz,Khz,MHz)"
                try:
                    clock = int(value)
                except ValueError as emsg:
                    raise Exception("Clock value should be integer, change units if necessary")
                self.clock = clock * freq_multiplier_units.get(unit) #Hz
                assert self.clock <= 100000000, "Clock frequency too large"
                self.timestep = int(1e9/self.clock) #ns
        if i == 1: # Clock select
            assert part in self.clockselect.keys(), "Undefined clock select"
            self.clock_select = self.clockselect.get(part)
        else:
            self.clock_select = 0 # auto by default
        if self.clock_select != 3:
            assert self.clock == 100_000_000, "Clock select and clock freq don't agree"

    def set_evars(self, evars_cols):
        self.evars = [0, 0, 0, 0] # Default to 0
        assert len(evars_cols) <= 4, "Too many external vars"
        for i, val in enumerate(evars_cols):
            val = int(val)
            assert val < 65536, "External variable overflow"
            self.evars[i] = val

    def set_ivars(self, ivars_cols):
        self.ivars = [0, 0, 0, 0] # Default to 0
        assert len(ivars_cols) <= 4, "Too many internal vars"
        for i, val in enumerate(ivars_cols):
            val = int(val)
            assert val < 65536, "Internal variable overflow"
            self.ivars[i] = val

    def set_auxline_polarity(self, aux_cols):
        self.auxline = None
        part = aux_cols[0]
        assert part in ['0', '1', 'nim' ,'ttl'], "Undefined auxout"
        if part in ['0', 'nim']:
            self.auxline = 0
        elif part in ['1', 'ttl']:
            self.auxline = 1
        if not self.auxline:
            self.auxline = 0 # Set to NIM by default

    def set_DACconfig(self, dac_config_cols):
        self.dacconfig = None
        part = dac_config_cols[0]
        assert part in self.dacselect.keys(), f"Undefined DAC config"
        self.dacconfig = self.dacselect.get(part)

    def set_patgenversion(self, patgen_ver_cols):
        self.patgen_ver = None
        part = patgen_ver_cols[0]
        assert part in ['32bit', '64bit']
        if part == '32bit':
            self.legacy = True
        elif part == '64bit':
            self.legacy = False
        else:
            self.legacy = True
    pass

class SeqBlock(Block):
    def __init__(self, block_id, content):
        super().__init__(block_id, content)
        self.block_type = "sequence"
        self.comment = []
        self.sequence = []

    def process_sequence(self):
        for i, line in enumerate(self.parse_contents()):
            if self.is_comment(line) and i == 0:
                self.trigger_name  = line[1:]
                continue
            elif self.is_comment(line):
                self.comment.append(line)
            cols = self.get_cols(line)

    pass

class TriggerBlock(Block):
    def __init__(self, block_id, content):
        super().__init__(block_id, content)
        self.block_type = "trigger"
        self.comment = []
        self.rate_defined = None
        self.count_defined = None
        self.trigger_grammar = ["extinput", "chan", "rate",
                "count", "success", "failure", "dac"]

    def process_trigger(self):
        for i, line in enumerate(self.parse_contents()):
            if self.is_comment(line) and i == 0:
                self.trigger_name = line[1:]
                continue
            elif self.is_comment(line):
                self.comment.append(line)
            cols = self.get_cols(line)
            first_col = cols[0]
            next_cols = cols[1:]
            assert first_col in self.trigger_grammar, f"{first_col} doesn't match syntax"
            if first_col == self.trigger_grammar[0]:
                self.set_exinput(next_cols)
            elif first_col == self.trigger_grammar[1]:
                self.set_chan(next_cols)
            elif first_col == self.trigger_grammar[2]:
                self.set_rate(next_cols)
            elif first_col == self.trigger_grammar[3]:
                self.set_count(next_cols)
            elif first_col == self.trigger_grammar[4]:
                self.set_success(next_cols)
            elif first_col == self.trigger_grammar[5]:
                self.set_failure(next_cols)
            elif first_col == self.trigger_grammar[6]:
                self.set_dac(next_cols)

    def set_exinput(self, line):
        part = line[0]
        assert part in ['e1', 'e2', 'e3', 'e4']
        self.external_input = int(part[1:])

    def set_chan(self, line):
        self.chan, comment = self.chan_on(','.join(line))
        self.comment.append(comment)

    def set_rate(self, line):
        line = self.eat_space_between_units(line)
        for i, part in enumerate(line):
            if i == 0: # Clock value and unit
                value, unit = self.split_unit(part)
                assert unit in freq_multiplier_units.keys(), "Undefined frequency units.(Hz,Khz,MHz)"
                try:
                    rate = int(value)
                except ValueError as emsg:
                    raise Exception("Clock value should be integer, change units if necessary")
                self.rate = rate * freq_multiplier_units.get(unit) #Hz
        if self.rate_defined == None and self.count_defined == None:
            self.rate_defined = True
        else:
            raise Exception("Use only RATE or COUNT, not both")

    def set_count(self, line):
        line = self.eat_space_between_units(line)
        for i, part in enumerate(line):
            if i == 0:
                try:
                    self.count = int(part)
                except ValueError as emsg:
                    raise Exception("Count value should be integer, change units if necessary")
            elif i == 1:
                assert part == "in"
            elif i == 2:
                value, unit = self.split_unit(part)
                try:
                    time_span = int(value)
                except ValueError as emsg:
                    raise Exception("Time span should be integer, change units if necessary")
                assert unit in time_multiplier_units.keys(), "Undefined time units. ns, us, ms)"
                self.time_span = time_span * time_multiplier_units.get(unit) #ns

        if self.rate_defined == None and self.count_defined == None:
            self.count_defined = True
        else:
            raise Exception("Use only RATE or COUNT, not both")


    def set_success(self, outcome):
        self.success = outcome[0]

    def set_failure(self, outcome):
        self.failure = outcome[0]

    def check_consistent(self, success = None, failure = None):
        if success is not None:
            assert success == self.success, "Success logic doesn't match Block"
        if failure is not None:
            assert failure == self.failure, "Failure logic doesn't match Block"
        return

    def set_dac(self, line):
        pass


class LoopBlock(Block):
    def __init__(self, block_id, content):
        super().__init__(block_id, content)
        self.block_type = "loop"
    pass

class BranchBlock(Block):
    def __init__(self, block_id, content):
        super().__init__(block_id, content)
        self.block_type = "branch"
    pass

def label_blocks(key):
    key = key.lower()
    if key.startswith("control"):
        return ControlBlock
    elif key.startswith("seq"):
        return SeqBlock
    elif key.startswith("trigger"):
        return TriggerBlock
    elif key.startswith("loop"):
        return LoopBlock
    elif key.startswith("branch"):
        return BranchBlock
    else:
        raise NotImplementedError(f"{key} not implemented.")

# Example usage
if __name__ == "__main__":
    parser = MermaidParser('v2.txt')
    parser.parse()
    blocks = {}
    for key, value in parser.get_blocks().items():
        cla = label_blocks(key)
        blocks[key] = cla(key,value)
