import configargparse
import re
import warnings

from math import ceil

# === UnitConverter ===
class UnitConverter:
    """
    Centralized utilities for frequency and time unit conversions.

    Supported frequency units: MHz, kHz, Hz.
    Supported time units: ms, us, ns.

    Example:
        >>> UnitConverter.freq(10, 'kHz')
        10000
        >>> UnitConverter.time(5, 'us')
        5000
    """
    freq_units = {'mhz': 1_000_000, 'khz': 1_000, 'hz': 1}
    time_units = {'ms': 1_000_000, 'us': 1_000, 'ns': 1}

    @staticmethod
    def freq(value, unit):
        """
        Convert frequency value and unit to Hz.

        Args:
            value (int): Frequency value.
            unit (str): Frequency unit ('MHz', 'kHz', 'Hz').

        Returns:
            int: Frequency in Hz.

        Raises:
            ValueError: If unit is not supported.
        """
        unit = unit.lower()
        if unit not in UnitConverter.freq_units:
            raise ValueError(f"Unknown frequency unit: {unit}")
        return int(value) * UnitConverter.freq_units[unit]

    @staticmethod
    def time(value, unit):
        """Convert time with unit (e.g. 5, 'us') to ns."""
        unit = unit.lower()
        if unit not in UnitConverter.time_units:
            raise ValueError(f"Unknown time unit: {unit}")
        return int(value) * UnitConverter.time_units[unit]

    @staticmethod
    def parse_value_unit(s: str):
        """Split '10ms' into ('10','ms'), or raise ValueError."""
        match = re.match(r"(\d+)([a-zA-Z]+)", s.strip())
        if match:
            return match.groups()
        raise ValueError(f"Cannot parse value and unit from '{s}'")

BLOCK_PATTERN_SINGLE = re.compile(r'^(\w+)\s*\[(.+)\]$')
BLOCK_PATTERN_BEGIN = re.compile(r'^(\w+)\s*\[(.*)$')
LOOP_PATTERN_SINGLE = re.compile(r'^subgraph\s*(\w+)\s*\[(.+)\]$')
LOOP_PATTERN_BEGIN = re.compile(r'^subgraph\s*(\w+)\s*\[(.*)$')
LOGIC_PATTERN = re.compile(r'^(\w+)\s*-->\s*(\|\w+\|)?\s*(\w+)$')

class MermaidParser:
    """
    Parses a Mermaid-like syntax file defining digital pattern generator blocks and their logical connections.
    
    Args:
        file_path (str): Path to the Mermaid-like input file.

    Attributes:
        blocks (dict): Maps block IDs to their content strings.
        logic (list): List of tuples representing logical connections between blocks, e.g., (block_start, block_end, condition).

    Example:
        Input file format:
            blockA [ content ]
            blockB [ more content ]
            blockA --> blockB

        Usage:
            parser = MermaidParser("input.txt")
            parser.parse()
            blocks = parser.get_blocks()
            logic = parser.get_logic()
    """
    def __init__(self, file_path):
        """
        Initialize the MermaidParser with the input file path.

        Args:
            file_path (str): Path to the input file to parse.
        """
        self.file_path = file_path
        self.blocks = {}
        self.logic = []

    def parse(self):
        """
        Parse the input file, populating 'blocks' and 'logic' attributes.
        Handles single-line blocks, multi-line blocks, loop blocks, and logic connections.
        """
        mermaid_comment = '%%'
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
        Detect the start of a multi-line loop block.

        Args:
            line (str): Line to check.

        Returns:
            bool: True if a loop block begins here, else False.
        """
        return self.match_block(line, LOOP_PATTERN_BEGIN)

    def start_multi_block(self, line):
        """
        Detect the start of a multi-line block.

        Args:
            line (str): Line to check.

        Returns:
            bool: True if a multi-line block begins here, else False.
        """
        return self.match_block(line, BLOCK_PATTERN_BEGIN)

    def match_block(self, line, pattern):
        """
        Generic helper to match a line against a block start pattern.

        Args:
            line (str): The line to check.
            pattern (re.Pattern): Compiled regex pattern.

        Returns:
            bool: True if a block match is found, else False.
        """
        start_match = pattern.match(line)
        if start_match and not line.endswith(']'):
            self.current_block_id, first_line = start_match.groups()
            self.current_block_lines = [first_line]
            return True

    def end_of_loop(self, line):
        """
        Check if a line marks the end of a loop block.

        Args:
            line (str): The line to check.

        Returns:
            bool: True if this is an 'end' line.
        """
        if line.startswith('end'):
            return True
        else:
            return False

    def get_single_loop_block(self, line):
        """
        Parse a single-line loop block.

        Args:
            line (str): The line to check.

        Returns:
            bool: True if a single-line loop block is found and added.
        """
        match = LOOP_PATTERN_SINGLE.match(line)
        if match:
            block_id, content = match.groups()
            self.current_block_id = block_id
            self.current_block_lines = [content]
            return True

    def end_of_line(self, line):
        """
        Check if a line marks the end of a block (i.e., ends with ']').

        Args:
            line (str): The line to check.

        Returns:
            bool: True if the line ends a block.
        """
        if line.endswith(']'):
            return True
        else:
            return False

    def block_join(self, line):
        """
        Join lines to complete a multi-line block and add it to blocks.

        Args:
            line (str): The final line of the block.
        """
        self.current_block_lines.append(line[:-1])
        self.blocks[self.current_block_id] = "\n".join(self.current_block_lines).strip()
        return

    def block_append(self, line):
        """
        Append a line to the current block being parsed.

        Args:
            line (str): The line to append.
        """
        self.current_block_lines.append(line)
        return

    def match_logic(self, line):
        """
        Parse a line for logical connections between blocks and update logic.
            e.g:
            key1 --> key2
            key1 --> |key3| key2
        Args:
            line (str): The line to check.

        """
        logic_match = LOGIC_PATTERN.match(line)
        if logic_match:
            if logic_match.lastindex == 3: # Has 3 information
                self.logic.append((logic_match.group(1),
                    logic_match.group(3),logic_match.group(2)))
            else:
                self.logic.append((logic_match.group(1), logic_match.group(2)))

    def ignore_comments(self, line):
        """
        Parses line and remove comments, empty line or flowchart keyword

        Args:
            line (str): The line to check.

        Returns:
            bool: True if the line should be ignored.
        """
        mermaid_comment = '%%'
        if not line or line.startswith("flowchart") or \
        line.startswith(mermaid_comment):
            return True
        else:
            return False

    def get_single_line_block(self, line):
        """  
        Parses line  and looks for single line block
        block_id [ content ]

        Args:
            line (str): The line to check.

        Returns:
            bool: True if a single-line block is found and added.
        """
        match = BLOCK_PATTERN_SINGLE.match(line)
        if match:
            block_id, content = match.groups()
            self.blocks[block_id] = content.strip()
            return True
        else:
            return False

    def get_blocks(self):
        """
        Get the parsed blocks.

        Returns:
            dict: The blocks dictionary.
        """
        return self.blocks

    def get_logic(self):
        """
        Get the parsed logic connections.

        Returns:
            list: The logic list.
        """
        return self.logic

class Block(MermaidParser):
    """
    Base class for representing a block in the pattern generator.

    This class provides common functionalities for parsing block content,
    handling comments, and extracting channel, DAC, and time information.
    Specific block types (Control, Sequence, Trigger, Loop, Branch)
    inherit from this class.

    Args:
        block_id (str): The unique identifier for the block.
        content (str): The raw string content of the block.
    """
    def __init__(self, block_id, content):
        """
        Initializes a Block instance.

        Args:
            block_id (str): The unique identifier for the block.
            content (str): The raw string content of the block.
        """
        self.block_id = block_id
        self.content = content
        self.first_row = None
        self.last_row = None
        self.written = False

    def split_comments(self,line):
        """
        Splits a line into its content and an optional comment part.

        Comments are expected to start with '#'.

        Args:
            line (str): The input line.

        Returns:
            tuple: A tuple containing the line content (str) and the comment (str).
                   If no comment is found, the comment string is empty.
        """
        text = line.split("#",1)
        if len(text)>1:
            line = text[0]
            comment = "#" + text[1]
        else:
            line = text[0]
            comment = ""
        return line, comment

    def get_cols(self, line):
        """
        Splits a line into columns based on delimiters (',', ' ', '\t')
        and handles comments.

        Args:
            line (str): The input line.

        Returns:
            list: A list of strings, where each string is a column.
                  Comments are appended as the last element if present.
        """
        line, comment = self.split_comments(line)
        delimiter = ",| |\t"
        line = line.lower()
        cols = list(filter(None, re.split(delimiter,line)))
        if comment:
            cols.append(comment)
        return cols

    def chan_on(self, chan_string):
        """
        Parses a channel string and returns a list of active channel numbers.

        The string can contain individual numbers or ranges (e.g., "1-3").
        Example: "0 2-4 7" -> [0, 2, 3, 4, 7]

        Args:
            chan_string (str): The string defining active channels.

        Returns:
            list: A sorted list of unique active channel integers.
        """
        chan_list = []
        for part in self.get_cols(chan_string):
            if '-' in part:
                start, end = map(int, part.split('-'))
                chan_list.extend(range(start, end + 1))
            else:
                chan_list.append(int(part))
        return list(set(chan_list)) # remove duplicate

    def dac_update(self, dac_string):
        """
        Parses a DAC string and returns a dictionary of DAC channel-value pairs.

        Format: "ch:val ch:val ..."
        Values can be integers or float voltages (which are converted to 16-bit).
        Example: "0:100 1:2.5V" -> {0: 100, 1: <16-bit value for 2.5V>}

        Args:
            dac_string (str): The string defining DAC updates.

        Returns:
            dict: A dictionary mapping DAC channel numbers (int) to their values (int).
        """
        dac_list = []
        dac_value = []
        for part in self.get_cols(dac_string):
            ch, val = part.split(":")
            dac_list.append(int(ch))
            if val.isdigit():
                dac_value.append(int(val))
            else:
                val =  self.volt_to_16bit(float(val))
                dac_value.append(val)
        return dict(zip(dac_list, dac_value))

    def parse_contents(self):
        """
        Splits the raw block content into a list of lines.

        Returns:
            list: A list of strings, where each string is a line from the block content.
        """
        return self.content.split('\n')

    def is_comment(self, line):
        """
        Checks if a given line is a comment line (starts with '#').

        Args:
            line (str): The input line.

        Returns:
            bool: True if the line is a comment, False otherwise.
        """
        if line.strip().startswith("#"):
            return True
        else:
            return False

    def eat_space_between_units(self, l):
        """
        Merges numerical values with their units if they are separated by space.

        Example: ["10", "ms"] -> ["10ms"]

        Args:
            l (list): A list of strings (columns).

        Returns:
            list: The modified list with values and units merged.
        """
        t = [x in UnitConverter.time_units for x in l]
        f = [x in UnitConverter.freq_units for x in l]
        for i, x in enumerate(t):
            if x:
                l[i-1] += l[i]
                l.pop(i)

        for i, x in enumerate(f):
            if x:
                l[i-1] += l[i]
                l.pop(i)

        return l

    def get_dac(self, cols):
        """
        Extracts DAC information from a list of columns.

        Expects the first column to be 'dac' (case-insensitive).

        Args:
            cols (list): A list of strings representing columns from a line.

        Returns:
            tuple: A tuple containing:
                - dac_updates (dict): DAC channel-value pairs.
                - comments (str): Any comments found on the line.
                - remaining_cols (list): The columns remaining after DAC parsing.
        """
        assert cols[0].lower() == 'dac', "Keyword missing"
        line = ','.join(cols[1:])
        line, comments = self.split_comments(line)
        cols = []
        return self.dac_update(line), comments, cols

    def volt_to_16bit(self,val):
        """
        Converts a voltage value to its 16-bit representation.

        Args:
            val (float): The voltage value (between -10.3V and 10.3V).

        Returns:
            int: The 16-bit integer representation of the voltage.

        Raises:
            AssertionError: If the voltage is out of range or conversion is unexpected.
        """
        slope = 0.00031433585
        if val > 10.3 or val < -10.3:
            assert "DAC float value out of range. -10.3 < V < 10.3"
        elif val > 0:
            ret_val = int(val/slope)
        elif val < 0:
            ret_val = int(0xffff + int(val/slope))
        else:
            ret_val = 0
        assert ret_val>=0 and ret_val < 65535, "Something strange"
        return ret_val

    def set_dac(self, line):
        """
        Placeholder method for setting DAC values.
        Currently not implemented.

        Args:
            line (list): A list of strings representing parts of a DAC command.
        """
        self.dac = self.dac_update(line)

    def get_chan(self, cols):
        """
        Extracts active channel information from a list of columns.

        Expects the first column to be 'chan' (case-insensitive).
        Can optionally be followed by 'dac' information.

        Args:
            cols (list): A list of strings representing columns from a line.

        Returns:
            tuple: A tuple containing:
                - active_channels (list): A list of active channel numbers.
                - comments (str): Any comments found on the line.
                - remaining_cols (list): Columns related to DAC or empty if none.
        """
        assert cols[0].lower() == 'chan', "Keyword missing"
        try:
            dac_idx = cols.index('dac')
            line = ','.join(cols[1:dac_idx])
            comments = ''
            cols = cols[dac_idx:]
        except ValueError:
            line = ','.join(cols[1:]) # without dac,
            cols = []
        line, comments = self.split_comments(line)
        return self.chan_on(line), comments, cols

    def set_chan(self, line):
        """
        Sets the active channels for the block.

        Args:
            line (list): A list of strings representing channel information.
                         These are joined and parsed by `chan_on`.
        """
        self.chan = self.chan_on(','.join(line))

    def set_exinput(self, line):
        """
        Sets the external input channel used by the block.

        The input channel must be one of 'e1', 'e2', 'e3', or 'e4'.
        This method sets `self.external_input` to the integer part (1, 2, 3, or 4).

        Args:
            line (list): A list of strings, where the first element is the
                         external input designator (e.g., "e1").

        Raises:
            AssertionError: If the input designator is not valid.
        """
        part = line[0]
        assert part in ['e1', 'e2', 'e3', 'e4']
        self.external_input = int(part[1:])

    def assert_grammar(self, key, grammar):
        """
        Checks if a given key is present in the expected grammar.

        Args:
            key (str): The keyword to check.
            grammar (list or dict): A collection of valid keywords.

        Raises:
            ValueError: If the key is not found in the grammar.
        """
        if key not in grammar:
            raise ValueError(f"{key} doesn't match syntax")

    def get_time(self, cols):
        """
        Extracts time information (value and unit) from columns and converts to nanoseconds.

        Time can be specified as "value_unit" (e.g., "10ns") or "value unit" (e.g., "10 ns").

        Args:
            cols (list): A list of strings representing columns. The time information
                         is expected at the beginning of this list.

        Returns:
            tuple: A tuple containing:
                - time_ns (int): The time value in nanoseconds.
                - remaining_cols (list): The columns remaining after time parsing.
        """
        try:
            value, unit = UnitConverter.parse_value_unit(cols[0])
            cols.pop(0)
        except ValueError:
            value = cols[0]
            unit = cols[1]
            cols.pop(0)
            cols.pop(0)
        finally:
            time = UnitConverter.time(value, unit)
        return time, cols

class ControlBlock(Block):
    """
    Represents a 'control' block in the pattern generator.

    This block defines global configuration settings for the pattern generator,
    such as clock frequency, variable initial values, DAC configurations, etc.

    Args:
        block_id (str): The unique identifier for the block (e.g., "control").
        content (str): The raw string content of the control block.
    """
    def __init__(self, block_id, content):
        """
        Initializes a ControlBlock instance with default values and grammar.
        """
        super().__init__(block_id, content)
        self.block_type = "control"
        self.auxconfig = 0
        self.start_address = 0 # Default to 0
        self.ivars = [0, 0, 0, 0] # Default to 0
        self.evars = [0, 0, 0, 0] # Default to 0
        self.auxline_pol = 0 # Set to NIM by default
        self.clock_select = 0 # auto by default
        self.level = 0 # Set to NIM by default
        self.dacconfig = 0 # Set to static by default
        self.patgen_128bit = False # Set to 64bit version by default
        self.dacs = [0,0,0,0,0,0,0,0] # Static DAC values
        self.inthreshold = 59000 # Nim by default


        self.auxselect = {'normal': 0, 'delayed':1, 'main':2,'ref':3}
        self.clockselect = {'auto': 0, 'external':1, 'internal':2,'direct':3}
        self.dacselect = {'static': 0, 'single':1, 'half':2,'full':3}
        self.control_grammar = ["clock", "evars", "ivars", "auxout",
                "dacconfig", "version", "inlevel", "auxconfig",
                "startaddress", "dacstatic"]

    def process_control(self):
        """
        Parses the content of the control block and sets the configuration attributes.

        Iterates through each line of the block content, identifies the control
        command, and calls the appropriate setter method.
        """
        for line in self.parse_contents():
            cols = self.get_cols(line)
            first_col = cols[0]
            next_cols = cols[1:]
            self.assert_grammar(first_col, self.control_grammar)
            # Python 3.10+ match/case equivalent:
            # match first_col:
            #     case "clock": self.set_clock(next_cols)
            #     case "evars": self.set_evars(next_cols)
            #     ...
            if first_col == self.control_grammar[0]: # clock
                self.set_clock(next_cols)
            elif first_col == self.control_grammar[1]: # evars
                self.set_evars(next_cols)
            elif first_col == self.control_grammar[2]: # ivars
                self.set_ivars(next_cols)
            elif first_col == self.control_grammar[3]: # auxout
                self.set_auxline_polarity(next_cols)
            elif first_col == self.control_grammar[4]: # dacconfig
                self.set_DACconfig(next_cols)
            elif first_col == self.control_grammar[5]: # version
                self.set_patgenversion(next_cols)
            elif first_col == self.control_grammar[6]: # inlevel
                self.set_external_input_polarity(next_cols)
            elif first_col == self.control_grammar[7]: # auxconfig
                self.set_auxconfig(next_cols)
            elif first_col == self.control_grammar[8]: # startaddress
                self.set_startaddress(next_cols)
            elif first_col == self.control_grammar[9]: # dacstatic
                self.set_staticDAC(next_cols)

    def set_clock(self, clock_cols):
        """
        Sets the clock frequency and selection mode.

        Args:
            clock_cols (list): Columns containing clock information.
                               Example: ["100mhz", "auto"]

        Raises:
            AssertionError: If clock frequency is too high or settings are inconsistent.
        """
        clock_cols = self.eat_space_between_units(clock_cols)
        for i, part in enumerate(clock_cols):
            if i == 0: # Clock value and unit
                value, unit = UnitConverter.parse_value_unit(part)
                self.clock = UnitConverter.freq(value, unit)
                assert self.clock <= 100_000_000, "Clock frequency too large"
                self.timestep = int(1e9/self.clock) #ns
        if i == 1: # Clock select
            assert part in self.clockselect.keys(), "Undefined clock select"
            self.clock_select = self.clockselect.get(part)
        else:
            self.clock_select = 0 # auto by default
        if self.clock_select != 3: # direct mode allows any clock
            assert self.clock == 100_000_000, "Clock select and clock freq don't agree for non-direct modes"

    def set_evars(self, evars_cols):
        """
        Sets the initial values for external variables (evars).

        Args:
            evars_cols (list): A list of up to 4 integer values for evars.

        Raises:
            AssertionError: If more than 4 evars are provided or a value overflows.
        """
        assert len(evars_cols) <= 4, "Too many external vars"
        for i, val in enumerate(evars_cols):
            val = int(val)
            assert val < 65536, "External variable overflow (must be < 65536)"
            self.evars[i] = val

    def set_ivars(self, ivars_cols):
        """
        Sets the initial values for internal variables (ivars).

        Args:
            ivars_cols (list): A list of up to 4 integer values for ivars.

        Raises:
            AssertionError: If more than 4 ivars are provided or a value overflows.
        """
        assert len(ivars_cols) <= 4, "Too many internal vars"
        for i, val in enumerate(ivars_cols):
            val = int(val)
            assert val < 65536, "Internal variable overflow (must be < 65536)"
            self.ivars[i] = val

    def set_auxconfig(self, aux_cols):
        """
        Sets the auxiliary output line configuration.

        Args:
            aux_cols (list): A list containing the auxline selection mode
                             (e.g., ["normal"], ["delayed"]).

        Raises:
            AssertionError: If the auxline selection mode is undefined.
        """
        part = aux_cols[0]
        assert part in self.auxselect.keys(), "Undefined auxline select"
        self.auxconfig = self.auxselect.get(part)

    def set_startaddress(self, aux_cols):
        """
        Sets the starting address for the pattern execution.

        Args:
            aux_cols (list): A list containing the start address (integer).

        Raises:
            AssertionError: If the start address is out of range (< 512).
        """
        part = int(aux_cols[0])
        assert part < 512, "Start address out of range (must be < 512)"
        self.start_address = part


    def set_auxline_polarity(self, aux_cols):
        """
        Sets the polarity for the auxiliary output line.

        Args:
            aux_cols (list): A list containing the polarity setting
                             ("0", "1", "nim", or "ttl").

        Raises:
            AssertionError: If the polarity setting is undefined.
        """
        part = aux_cols[0]
        assert part in ['0', '1', 'nim' ,'ttl'], "Undefined auxout polarity"
        if part in ['0', 'nim']:
            self.auxline_pol = 0
        elif part in ['1', 'ttl']:
            self.auxline_pol = 1

    def set_external_input_polarity(self, aux_cols):
        """
        Sets the polarity for the external input level.

        Args:
            aux_cols (list): A list containing the polarity setting
                             ("0", "1", "nim", or "ttl").

        Raises:
            AssertionError: If the polarity setting is undefined.
        """
        part = aux_cols[0]
        assert part in ['0', '1', 'nim' ,'ttl'], "Undefined external input polarity"
        if part in ['0', 'nim']:
            self.level = 0
        elif part in ['1', 'ttl']:
            self.level = 1


    def set_DACconfig(self, dac_config_cols):
        """
        Sets the DAC configuration mode.

        Args:
            dac_config_cols (list): A list containing the DAC configuration mode
                                    (e.g., ["static"], ["full"]).

        Raises:
            AssertionError: If the DAC configuration mode is undefined.
        """
        part = dac_config_cols[0]
        assert part in self.dacselect.keys(), f"Undefined DAC config: {part}"
        self.dacconfig = self.dacselect.get(part)

    def set_staticDAC(self, dac_vals):
        """
        Sets the static values for the DAC channels.

        These values are used if the `dacconfig` is 'static' or for DACs
        not actively updated in other modes.

        Args:
            dac_vals (list): A list of strings defining DAC channel-value pairs
                             (e.g., ["0:1.0V", "1:2000"]).
        """
        line = ','.join(dac_vals)
        dac_dict = self.dac_update(line) # Uses Block.dac_update
        for dac_chan, val in dac_dict.items():
            self.dacs[dac_chan] = val

    def set_patgenversion(self, patgen_ver_cols):
        """
        Sets the pattern generator version (64-bit or 128-bit).

        This affects whether DAC functionality is available.

        Args:
            patgen_ver_cols (list): A list containing the version string
                                    ("64bit" or "128bit").

        Raises:
            AssertionError: If the version string is invalid.
        """
        part = patgen_ver_cols[0]
        assert part in ['128bit', '64bit'], f"Invalid pattern generator version: {part}"
        if part == '128bit':
            self.patgen_128bit = True
        elif part == '64bit':
            self.patgen_128bit = False

    def process(self):
        """
        Main processing method for the ControlBlock.
        Calls `process_control` to parse and apply settings.
        """
        self.process_control()

class SeqBlock(Block):
    """
    Represents a 'sequence' block in the pattern generator.

    A sequence block defines a series of steps, each with a duration,
    active digital channels, optional DAC updates, and optional use of
    internal variables (ivars) for looping/timing.

    The first line of a sequence block, if it's a comment, is taken as
    the sequence name.

    Attributes:
        block_type (str): Set to "sequence".
        last_step_is_loop (bool): True if the last step in the sequence uses an ivar.
        sequence_name (str): Name of the sequence (from the first comment line).
        sequence (list): A list of dictionaries, where each dictionary represents
                         a step in the sequence. Each step dict contains:
                         'time' (int): Duration in ns.
                         'chan' (list): Active digital channels.
                         'use_ivar' (int or None): Index of ivar used (0-3), or None.
                         'dac' (dict): DAC channel-value pairs.
                         'comments' (str): Comments for the step.
    """
    def __init__(self, block_id, content):
        """
        Initializes a SeqBlock instance.
        """
        super().__init__(block_id, content)
        self.block_type = "sequence"
        self.last_step_is_loop = False
        self.sequence_name = ""
        self.sequence = []

    def process_seq(self):
        """
        Parses the content of the sequence block to populate the `sequence` list.

        The first line, if a comment, sets `self.sequence_name`.
        Each subsequent line is parsed into a sequence step.
        """
        for i, line in enumerate(self.parse_contents()):
            if i == 0 and self.is_comment(line):
                self.sequence_name  = line[1:].strip() # Get name from comment
                continue
            cols = self.get_cols(line)
            self.add_seq_from_cols(cols)

    def add_seq_from_cols(self, cols):
        """
        Parses a list of columns (from a line) and adds a new step to `self.sequence`.

        Extracts time, ivar usage, channel information, and DAC updates.

        Args:
            cols (list): A list of strings representing columns from a sequence line.
        """
        time, cols = self.get_time(cols)
        use_ivar, cols = self.get_ivar(cols) # Expects 'use_ivar <idx>' or nothing
        chan, comments1, cols = self.get_chan(cols) # Expects 'chan <channels>'
        if cols: # Remaining columns are assumed to be DAC info
            dac, comments2, cols = self.get_dac(cols) # Expects 'dac <dac_updates>'
        else:
            dac = {}
            comments2 = ""
        self.sequence.append({'time' : time,
                              'chan' : chan,
                              'use_ivar' : use_ivar,
                              'dac' : dac,
                              'comments' : (comments1 + " " + comments2).strip(),
                              })


    def get_ivar(self, cols):
        """
        Extracts 'use_ivar' information from a list of columns.

        Looks for "use_ivar <index>" pattern. The index must be 0, 1, 2, or 3.

        Args:
            cols (list): A list of strings (columns).

        Returns:
            tuple: A tuple containing:
                - ivar_index (int or None): The ivar index (0-3) if found, else None.
                - remaining_cols (list): The columns after 'use_ivar' parsing.

        Raises:
            AssertionError: If 'use_ivar' is present but the index is invalid.
        """
        try:
            index = cols.index('use_ivar')
            ivar = int(cols[index+1])
            cols.pop(index) # remove 'use_ivar'
            cols.pop(index) # remove index value
        except ValueError: # 'use_ivar' not found
            ivar = None
        assert ivar in [None, 0, 1, 2, 3], f"Invalid ivar index: {ivar}"
        return ivar, cols

    def process(self):
        """
        Main processing method for the SeqBlock.
        Calls `process_seq` to parse the sequence definition.
        """
        self.process_seq()

class TriggerBlock(Block):
    """
    Represents a 'trigger' block in the pattern generator.

    A trigger block defines conditions based on an external input,
    event rate, or event count, and specifies subsequent blocks to
    execute based on success or failure of the trigger condition.

    The first line, if a comment, is taken as the trigger name.

    Attributes:
        block_type (str): Set to "trigger".
        trigger_name (str): Name of the trigger (from the first comment line).
        comment (list): List of comments found in the block.
        chan (list): Digital channels to set when this block is active. (Set by `set_chan`)
        dac (list): DAC updates when this block is active. (Set by `get_dac`)
        rate (int): Trigger rate in Hz (if `rate` is defined).
        count (int): Trigger count (if `count` is defined).
        time_span (int): Time span in ns for count-based trigger.
        success (str): Block ID to jump to on trigger success.
        failure (str): Block ID to jump to on trigger failure.
        external_input (int): External input channel (1-4) used. (Set by `set_exinput`)
        rate_defined (bool): True if rate is used for triggering.
        count_defined (bool): True if count is used for triggering.
    """
    def __init__(self, block_id, content):
        """
        Initializes a TriggerBlock instance.
        """
        super().__init__(block_id, content)
        self.block_type = "trigger"
        self.trigger_name = ""
        self.comment = []
        self.chan = [] # Populated by set_chan
        self.dac = []  # Populated by get_dac
        self.rate_defined = None
        self.count_defined = None
        self.trigger_grammar = ["extinput", "chan", "rate",
                "count", "success", "failure", "dac"]

    def process_trigger(self):
        """
        Parses the content of the trigger block to set its attributes.

        The first line, if a comment, sets `self.trigger_name`.
        Each subsequent line is parsed based on keywords defined in `trigger_grammar`.
        """
        for i, line in enumerate(self.parse_contents()):
            if self.is_comment(line) and i == 0:
                self.trigger_name = line[1:].strip()
                continue
            cols = self.get_cols(line)
            first_col = cols[0]
            next_cols = cols[1:]
            if self.is_comment(next_cols[-1]):
                self.comment.append(next_cols[-1])
            self.assert_grammar(first_col, self.trigger_grammar)

            if first_col == self.trigger_grammar[0]: # extinput
                self.set_exinput(next_cols) # Inherited from Block
            elif first_col == self.trigger_grammar[1]: # chan
                self.set_chan(next_cols) # Inherited from Block, sets self.chan
            elif first_col == self.trigger_grammar[2]: # rate
                self.set_rate(next_cols)
            elif first_col == self.trigger_grammar[3]: # count
                self.set_count(next_cols)
            elif first_col == self.trigger_grammar[4]: # success
                self.set_success(next_cols)
            elif first_col == self.trigger_grammar[5]: # failure
                self.set_failure(next_cols)
            elif first_col == self.trigger_grammar[6]: # dac
                self.dac = self.set_dac(next_cols) # Inherited from Block

    def set_rate(self, line):
        """
        Sets the trigger rate.

        Args:
            line (list): Columns defining the rate (e.g., ["100khz"]).

        Raises:
            Exception: If both rate and count are defined for the trigger.
        """
        line = self.eat_space_between_units(line)
        for i, part in enumerate(line):
            if i == 0: # Rate value and unit
                value, unit = UnitConverter.parse_value_unit(part)
                self.rate = UnitConverter.freq(value, unit)
        if self.rate_defined is None and self.count_defined is None:
            self.rate_defined = True
        else:
            raise Exception("Use only RATE or COUNT, not both, for a trigger block.")

    def set_count(self, line):
        """
        Sets the trigger count over a specified time span.

        Args:
            line (list): Columns defining count and time span
                         (e.g., ["10", "in", "1ms"]).

        Raises:
            Exception: If both rate and count are defined for the trigger.
            ValueError: If count value is not an integer.
            AssertionError: If "in" keyword is missing.
        """
        line = self.eat_space_between_units(line)
        for i, part in enumerate(line):
            if i == 0: # Count value
                try:
                    self.count = int(part)
                except ValueError:
                    raise ValueError("Count value should be an integer.")
            elif i == 1: # "in" keyword
                assert part.lower() == "in", "Keyword 'in' missing for count definition."
            elif i == 2: # Time span value and unit
                value, unit = UnitConverter.parse_value_unit(part)
                self.time_span = UnitConverter.time(value, unit)

        if self.rate_defined is None and self.count_defined is None:
            self.count_defined = True
        else:
            raise Exception("Use only RATE or COUNT, not both, for a trigger block.")


    def set_success(self, outcome):
        """
        Sets the block ID to jump to on trigger success.

        Args:
            outcome (list): A list containing the block ID string.
        """
        self.success = outcome[0]

    def set_failure(self, outcome):
        """
        Sets the block ID to jump to on trigger failure.

        Args:
            outcome (list): A list containing the block ID string.
        """
        self.failure = outcome[0]

    def check_consistent(self, success=None, failure=None):
        """
        Checks if the provided success/failure logic matches the block's settings.

        Used by the Translator to verify logic flow.

        Args:
            success (str, optional): Expected success block ID.
            failure (str, optional): Expected failure block ID.

        Raises:
            AssertionError: If the provided logic does not match the block's.
        """
        if success is not None:
            assert success == self.success, \
                f"Success logic mismatch: expected {self.success}, got {success}"
        if failure is not None:
            assert failure == self.failure, \
                f"Failure logic mismatch: expected {self.failure}, got {failure}"
        return

    def process(self):
        """
        Main processing method for the TriggerBlock.
        Calls `process_trigger` to parse the trigger definition.
        """
        self.process_trigger()

class LoopBlock(Block):
    """
    Represents a 'loop' block in the pattern generator.

    A loop block uses an internal variable (ivar) as a counter to repeat
    a sequence of other blocks or operations.

    The first line, if a comment, is taken as the loop name.
    The second line defines the ivar, its initial count, and optional
    channel/DAC settings for each iteration.
    Subsequent lines define the logic flow within the loop (connections to other blocks).

    Attributes:
        block_type (str): Set to "loop".
        loop_name (str): Name of the loop (from the first comment line).
        logic (list): Temporary list used by `match_logic` (inherited from MermaidParser via Block).
                      Should be cleared or handled carefully if `match_logic` is called directly.
        loop_logic (list): A list of logic connections (tuples) that form the body of the loop.
                           Each tuple is like: (source_block_id, target_block_id, condition_str).
        counter_var (int): Index of the ivar used for counting (0-3).
        counter_val (int): Initial value for the ivar counter.
        loop_set (dict): Contains settings for each loop iteration:
                         'chan' (list): Active digital channels.
                         'use_ivar' (int): The `counter_var`.
                         'dac' (dict): DAC channel-value pairs.
                         'comments' (str): Comments for the loop setup line.
    """
    def __init__(self, block_id, content):
        """
        Initializes a LoopBlock instance.
        """
        super().__init__(block_id, content)
        self.block_type = "loop"
        self.loop_name = ""
        self.logic = [] # Inherited from MermaidParser, used by self.match_logic
        self.loop_logic = [] # Stores logic specific to this loop block

    def process_loop(self):
        """
        Parses the content of the loop block to set its attributes.

        - First line (if comment): sets `self.loop_name`.
        - Second line: parses ivar, count, and optional channel/DAC settings using `get_ivar` and `get_chan`/`get_dac`.
        - Subsequent lines: parse as logic connections using `add_logic_from_line`.
        """
        for i, line in enumerate(self.parse_contents()):
            if i == 0 and self.is_comment(line):
                self.loop_name  = line[1:].strip()
                continue
            if i == 1: # ivar setup line
                cols = self.get_cols(line)
                # get_ivar for LoopBlock is specific, not from SeqBlock
                self.counter_var, self.counter_val, cols = self.get_ivar(cols)
                chan, comments1, cols = self.get_chan(cols)
                if cols:
                    dac, comments2, cols = self.get_dac(cols)
                else:
                    dac = {}
                    comments2 = ""
                self.loop_set={'chan' : chan,
                              'use_ivar' : self.counter_var, # Store which ivar is the counter
                              'dac' : dac,
                              'comments' : (comments1 + " " + comments2).strip(),
                              }
            else: # Logic lines within the loop
                self.add_logic_from_line(line)

    def add_logic_from_line(self, line):
        """
        Parses a line for a logic connection and adds it to `self.loop_logic`.

        Uses `self.match_logic` (inherited from MermaidParser via Block) which
        appends to `self.logic`. This method then moves the last added item
        from `self.logic` to `self.loop_logic`.

        Args:
            line (str): The line defining a logic connection.
        """
        self.match_logic(line) # Appends to self.logic
        if len(self.logic) > 0:
            self.loop_logic.append(self.logic.pop()) # Move from self.logic to self.loop_logic

    def get_ivar(self, cols):
        """
        Extracts ivar index and count value for the loop counter.

        Expects "ivar <index> <value>" followed by optional 'chan' or 'dac'.

        Args:
            cols (list): A list of strings (columns from the ivar setup line).

        Returns:
            tuple: A tuple containing:
                - ivar_index (int): The ivar index (0-3).
                - count_value (int): The initial count for the loop.
                - remaining_cols (list): Columns after ivar parsing (for chan/dac).

        Raises:
            AssertionError: If keyword 'ivar' is missing, index is invalid, or value is out of bounds.
        """
        assert cols[0].lower() == 'ivar', "Wrong keyword, expected 'ivar' for loop setup."
        ivar = int(cols[1])
        assert ivar in [0, 1, 2, 3], "Counter ivar index must be 0, 1, 2, or 3."
        val = int(cols[2])
        assert (val > 0 and val < 65536), "Counter value out of bounds (1-65535)."

        # Prepare remaining columns for further parsing (chan/dac)
        remaining_cols = cols[3:]
        return ivar, val, remaining_cols

    def process(self):
        """
        Main processing method for the LoopBlock.
        Calls `process_loop` to parse the loop definition.
        """
        self.process_loop()

class BranchBlock(Block):
    """
    Represents a 'branch' block in the pattern generator.

    A branch block makes a decision based on an external input's level (high or low)
    and jumps to a different block accordingly. It can also define a default
    timestep, digital channels, and DAC settings to apply while waiting for the input.

    The first line, if a comment, is taken as the branch name.

    Attributes:
        block_type (str): Set to "branch".
        branch_name (str): Name of the branch (from the first comment line).
        chan (list): Digital channels to set. (Populated by `get_chan` via `process_branch`)
        dac (list): DAC updates. (Populated by `get_dac` via `process_branch`)
        comment (list): List of comments found in the block. (Note: `self.comment` needs to be initialized in `__init__`)
        external_input (int): External input channel (1-4) used. (Set by `set_exinput`)
        high (str): Block ID to jump to if the external input is high.
        low (str): Block ID to jump to if the external input is low.
        timestep (int): Default time step in ns for this block, if specified.
    """
    def __init__(self, block_id, content):
        """
        Initializes a BranchBlock instance.
        """
        super().__init__(block_id, content)
        self.block_type = "branch"
        self.branch_name = ""
        self.chan = [] # Will be populated by get_chan if 'chan' keyword is present
        self.dac = []  # Will be populated by get_dac if 'dac' keyword is present
        self.comment = [] # Initialize comment list
        self.branch_grammar = ["extinput", "high", "low", "chan", "dac"]
        # timestep might be set directly if a line is just a time value

    def process_branch(self):
        """
        Parses the content of the branch block to set its attributes.

        The first line, if a comment, sets `self.branch_name`.
        Each subsequent line is parsed based on keywords in `branch_grammar`
        or as a direct time value.
        """
        for i, line in enumerate(self.parse_contents()):
            if self.is_comment(line) and i == 0:
                self.branch_name = line[1:].strip()
                continue
            cols = self.get_cols(line)
            if len(cols)>1:
                first_col = cols[0]
                next_cols = cols[1:]
                if self.is_comment(next_cols[-1]):
                    self.comment.append(next_cols[-1])
                self.assert_grammar(first_col, self.branch_grammar)

                if first_col == self.branch_grammar[0]: # extinput
                    self.set_exinput(next_cols) # Inherited from Block
                elif first_col == self.branch_grammar[1]: # high
                    self.set_high(next_cols)
                elif first_col == self.branch_grammar[2]: # low
                    self.set_low(next_cols)
                elif first_col == self.branch_grammar[3]:
                    self.get_chan(next_cols)
                elif first_col == self.branch_grammar[4]:
                    self.get_dac(next_cols)
                else:
                    self.timestep, _ = self.get_time(cols)
            else:
                self.timestep, _ = self.get_time(cols)
        pass

    def set_high(self, outcome):
        """
        Sets the block ID to jump to if the external input is high.

        Args:
            outcome (list): A list containing the block ID string.
        """
        self.high = outcome[0]

    def set_low(self, outcome):
        """
        Sets the block ID to jump to if the external input is low.

        Args:
            outcome (list): A list containing the block ID string.
        """
        self.low = outcome[0]

    def check_consistent(self, high=None, low=None):
        """
        Checks if the provided high/low logic matches the block's settings.

        Used by the Translator to verify logic flow.

        Args:
            high (str, optional): Expected 'high' block ID.
            low (str, optional): Expected 'low' block ID.

        Raises:
            AssertionError: If the provided logic does not match the block's.
        """
        if high is not None:
            assert high == self.high, \
                f"High logic mismatch for branch {self.block_id}: expected {self.high}, got {high}"
        if low is not None:
            assert low == self.low, \
                f"Low logic mismatch for branch {self.block_id}: expected {self.low}, got {low}"
        return

    def process(self):
        """
        Main processing method for the BranchBlock.
        Calls `process_branch` to parse the branch definition.
        """
        self.process_branch()

class BlockFactory:
    """
    Factory to create block objects based on block name/id.
    Register block classes using BlockFactory.register().
    """
    _registry = {}

    @classmethod
    def register(cls, prefix, block_cls):
        """
        Registers a block class with a given prefix.

        The factory uses these registered classes to create block instances.
        The prefix is matched against the beginning of a block's ID (case-insensitive).

        Args:
            prefix (str): The prefix string to associate with the block class.
            block_cls (type): The block class (e.g., `ControlBlock`, `SeqBlock`).
        """
        cls._registry[prefix.lower()] = block_cls

    @classmethod
    def create(cls, block_id, content):
        """
        Creates a block instance based on its ID.

        It iterates through the registered block types and instantiates the
        first one whose prefix matches the beginning of the `block_id`.

        Args:
            block_id (str): The unique identifier of the block.
            content (str): The raw content of the block.

        Returns:
            Block: An instance of the appropriate subclass of `Block`.

        Raises:
            NotImplementedError: If no registered block type matches the `block_id`.
        """
        for prefix, block_cls in cls._registry.items():
            if block_id.lower().startswith(prefix):
                return block_cls(block_id, content)
        raise NotImplementedError(f"Block type for ID '{block_id}' not implemented or registered.")


BlockFactory.register("control", ControlBlock)
BlockFactory.register("seq", SeqBlock)
BlockFactory.register("trigger", TriggerBlock)
BlockFactory.register("loop", LoopBlock)
BlockFactory.register("branch", BranchBlock)

class Translator:
    """
    Translates parsed Mermaid-like block definitions into a hardware-specific
    pattern file format (.dpatt).

    The Translator takes a dictionary of parsed blocks and a list of logic
    connections, processes them, and generates the output file content.
    It handles:
    - Processing configuration from the 'control' block.
    - Preprocessing all other blocks to determine their size in pattern rows.
    - Assigning start and end row addresses to each block based on logic.
    - Generating the 'writew' lines for each block's functionality.
    - Writing the final .dpatt file.
    """
    def __init__(self, blocks, logic, filein, fileout, hex=True, verbose=False):
        """
        Initializes the Translator.

        Args:
            blocks (dict): Dictionary of block_id to raw block content string,
                           as returned by MermaidParser.get_blocks().
            logic (list): List of logic connection tuples (source_id, target_id, condition_str),
                          as returned by MermaidParser.get_logic().
            filein (str): Name of the input Mermaid-like file (for logging).
            fileout (str): Path to the output .dpatt file.
            hex (bool): If True, output numerical values in hexadecimal format (except time).
            verbose (bool): If True, include more detailed comments in the output file.
        """
        self.blocks = {} # This will store processed Block objects
        self.hex = hex
        self.verbose = verbose
        self.logic = logic # Overall program flow logic
        self.config_bits = 0
        self.param_register = []
        self.new_dpatt_str = "" # String for the main pattern program
        self.dpatt_str = f"#This file was generated by gen3.py using {filein}\n\n" # Header for .dpatt
        self.fileout = fileout

        # Create and process each block object
        for key, value in blocks.items():
            block_obj = BlockFactory.create(key, value)
            self.blocks[key] = block_obj # Store the Block object instance
            block_obj.process() # Call the block's specific process() method

        # Default configuration bits for initial setup
        PARAMETERWRITE = 8 # Bit 3: Write to parameter RAM
        ADDRESSRESET = 4   # Bit 2: Reset address counter on jump
        TABLERESET = 1     # Bit 0: Reset table pointer

        self.process_config() # Process the 'control' block for global settings
        self.write_config(PARAMETERWRITE + ADDRESSRESET + TABLERESET) # Write initial config word
        self.write_param() # Write parameter register values

        self.preprocess_blocks() # Calculate row requirements and assign addresses
        self.process_logic() # Generate the 'writew' lines for the pattern
        self.write_out() # Write everything to the output file

    def write_out(self):
        """
        Writes the generated .dpatt content to the output file.
        Appends a "run;" command at the end.
        """
        with open(self.fileout, 'w') as f:
            f.write(self.dpatt_str) # Header, config, params
            f.write(self.new_dpatt_str) # Main pattern program
            f.write("\n\nrun; #Run sequence")

    def preprocess_blocks(self):
        """
        Preprocesses all blocks to determine their required number of pattern rows
        and assigns `first_row` and `last_row` attributes to each block.

        This involves:
        1. Calculating `num_rows` for each non-control block via `determine_num_rows`.
        2. Iterating through the main program `logic` to lay out blocks sequentially
           in memory, assigning `first_row` and `last_row` for each block and
           any nested blocks (like within a loop).
        """
        # Go through blocks and determine rows needed for each
        for block_id, block_obj in self.blocks.items():
            if block_obj.block_type == 'control':
                continue
            else:
                self.determine_num_rows(block)
        # Go through logic and deterimne start address and end address of each
        # block
        first = True
        count = 0
        for block, block_end, condition in self.logic:
            block = self.blocks[block]
            if first:
                block.first_row = 0
                count = block.first_row + block.num_rows
                block.last_row = count - 1
                first = False
                continue
            if block.first_row == None: # Need this since 0 is treated as False
                block.first_row = count
                count = block.first_row + block.num_rows
                block.last_row = count - 1
            if block.last_row == None:
                count = block.first_row + block.num_rows
                block.last_row = count - 1
            block_end = self.blocks[block_end]
            if block_end.first_row == None:
                block_end.first_row = count
                if block_end.block_type == 'loop':
                    count += 2 # 2 for loop load var and decrement counter
                    for block_loop, block_loop_end, condition_loop in \
                    block_end.loop_logic: # assume no nested loop
                        #print(block_loop, block_loop_end, condition_loop, count)
                        block_loop = self.blocks[block_loop]
                        if block_loop.first_row == None:
                            block_loop.first_row = count
                            count = block_loop.first_row + block_loop.num_rows
                            block_loop.last_row = count - 1
                        if block_loop.last_row == None:
                            count = block_loop.first_row + block_loop.num_rows
                            block_loop.last_row = count - 1
                        #print(block_loop.block_id, block_loop_end, condition_loop, count)
                if block_end.block_type == 'loop':
                    count += 2 # 2 for check and zero conndition address
                    block_end.last_row = count - 1
                else:
                    count += block_end.num_rows
                    block_end.last_row = count - 1

    def determine_num_rows(self, block):
        """
        Determines the number of hardware pattern rows required for a given block.

        Calls the appropriate `preprocess_<block_type>` method.

        Args:
            block (Block): The block object whose `num_rows` attribute will be set.
        """
        if block.block_type == 'sequence':
            self.preprocess_seq(block)
        elif block.block_type == 'trigger':
            self.preprocess_trigger(block)
        elif block.block_type == 'loop':
            self.preprocess_loop(block)
        elif block.block_type == 'branch':
            self.preprocess_branch(block)
        else:
            raise AssertionError(f"Unknown block type for row determination: {block.block_type}")

    def preprocess_branch(self, block):
        '''
            Branching can either use 1 or 2 rows.
            It depends on the block of the "low" branch.
            1) Check condition with high address
            (2) Low address if not the next row 
        '''
        low = block.low
        name = block.block_id
        for i, l in enumerate(self.logic):
            if l[0] == name and self.logic[i+1][0] == low:
                block.num_rows = 1
                break
            else:
                block.num_rows = 2

    def preprocess_trigger(self, block):
        """
        Sets `num_rows` for a TriggerBlock.
        Trigger blocks are allocated a fixed number of rows (currently 5)
        to accommodate various operations like loading variables, decrementing,
        and checking conditions.

        The 5 rows are typically for:
        1. Load evar (and ivar if needed for long time_span).
        2. Decrement ivar counter (if ivar used).
        3. Check non-zero ivar and branch (if ivar used).
        4. Check non-zero evar and branch to failure_row.
        5. Branch to success_row (if evar was zero).

        Args:
            block (TriggerBlock): The trigger block to process.
        """
        block.num_rows = 5

    def preprocess_loop(self, block):
        """
        Sets `num_rows` for a LoopBlock.
        Loop blocks are allocated a fixed number of rows (currently 4)
        for their control structure, plus rows for blocks inside the loop.
        The 4 rows are for:
        1. Load ivar (counter).
        2. Decrement ivar.
        3. Check ivar non-zero and branch to loop start.
        4. Branch to loop exit (when ivar is zero).
        Rows for blocks *inside* the loop are accounted for during the main
        `preprocess_blocks` logic traversal.

        Args:
            block (LoopBlock): The loop block to process.
        """
        # The num_rows for a loop block itself (control structure)
        block.num_rows = 4 # For load, decrement, check, and exit branching.
        # Rows for blocks *inside* the loop are added during the main preprocess_blocks logic traversal.

    def preprocess_seq(self, block):
        """
        Calculates `num_rows` for a SeqBlock based on its sequence steps.
        Each step contributes rows depending on its duration and use of ivars.

        Args:
            block (SeqBlock): The sequence block to process.
        """
        rows = 0
        seq_len = len(block.sequence) - 1
        for j, step in enumerate(block.sequence):
            time = step['time']
            i = step['use_ivar']
            ivar = self.ivars[i] if i else None
            if ivar:
                rows += 1 # For load
                if time/self.maxtimestep/ivar/2 <= 1:
                    rows += 2 # For decrement and check
                else: # Happens at >85.8 s with max ivar(65535)
                    rows += 2 + \
                    ceil(time/self.maxtimestep/ivar)# Additional line gives 43s
                if j == seq_len:
                    rows += 1 # Add one more line if loop is last of sequence
                    block.last_step_is_loop = True
            elif ceil(time/self.maxtimestep)<1:
                rows += 1 # For single step
            else:
                additional_rows = ceil(time/self.maxtimestep)
                if additional_rows >4:
                    warnings.warn(f"This time step uses {additional_rows} " + \
                            "rows of the pattern. Consider using ivar")
                rows += additional_rows # For steps without loops.
        block.num_rows = rows

    def process_logic(self):
        self.new_dpatt_str += "\nholdaddr; ramprog;\n"
        self.pattern_row = 0
        for block_start, block_end, condition in self.logic:
            start = self.blocks[block_start]
            end = self.blocks[block_end]
            if start.written:
                continue
            if start.block_type == 'trigger':
                #print(f"start {start.block_id}, end {end.block_id}, condition" +
                #f" {condition}")
                self.process_trigger_logic(start, end, condition)
            if start.block_type == 'sequence':
                self.process_seq_logic(start, end)
            if start.block_type == 'loop':
                self.process_loop_logic(start, end)
            if start.block_type == 'branch':
                self.process_branch_logic(start, end, condition)

    def process_branch_logic(self, branch_block, end, condition):
        count = 0
        ext_chan = branch_block.external_input
        dig_chan = {'chan' :branch_block.chan, 'dac': branch_block.dac}
        timestep = branch_block.timestep
        comment = ''
        special_bcheck_address_high = self.blocks[branch_block.high].first_row
        special_bcheck_address_low = self.blocks[branch_block.low].first_row
        special_bcheck = ((ext_chan+3)<<12)
        self.new_dpatt_str += self.writew_line(
                channels=dig_chan,
                time=timestep,
                address={'address' : special_bcheck_address_high,
                         'special' : special_bcheck,
                         'cond'    : None,
                         },
                comment=comment,
                )
        count +=1
        if branch_block.num_rows == 2:
            self.new_dpatt_str += self.writew_line(
                channels=dig_chan,
                time=timestep,
                address={'address' : special_bcheck_address_low,
                         'special' : None,
                         'cond'    : None,
                         },
                comment=comment,
                )
            count +=1
        branch_block.written = True
        #print("branch", count, num_rows)

    def process_loop_logic(self, loop_block, loop_end):
        count = 0
        self.new_dpatt_str += "\n#" + loop_block.block_id + "  " + \
                              loop_block.loop_name + "\n"

        ivar_chan = loop_block.counter_var
        dig_chan = {'chan': loop_block.loop_set['chan'],
                    'dac': loop_block.loop_set['dac']}
        load_timestep = self.timestep
        timestep = self.timestep
        comment  =loop_block.loop_set['comments']

        special_load = (1<<12) + ((2**ivar_chan)<<4)
        special_dec = (1<<12) + ((2**ivar_chan)<<8)
        special_icheck = ((12 + ivar_chan)<<12)
        icheck_row = loop_block.last_row - 1
        ivar = loop_block.counter_val

        self.new_dpatt_str += self.writew_line(
                channels=dig_chan,
                time=load_timestep,
                address={'address' : None,
                         'special' : special_load,
                         'cond'    : None,
                         },
                comment= f"Load internal counter {ivar_chan} " + comment,
                )
        repeat_icheck_address = self.pattern_row
        self.new_dpatt_str += self.writew_line(
                channels=dig_chan,
                time=timestep,
                address={'address' : None,
                         'special' : special_dec,
                         'cond'    : None,
                         },
                comment=f"Decrement {ivar_chan}, " + comment,
                )
        count += 2
        for block_start, block_end, condition in loop_block.loop_logic:
            start = self.blocks[block_start]
            if block_end == 'loop_check':
                end.block_id = 'loop_check'
                end.loop_check_row = icheck_row
            else:
                end = self.blocks[block_end]
            if start.written:
                continue
            if start.block_type == 'trigger':
                #print(f"start {start.block_id}, end {end.block_id}, condition" +
                #f" {condition}")
                self.process_trigger_logic(start, end, condition)
            if start.block_type == 'sequence':
                self.process_seq_logic(start, end)

        self.new_dpatt_str += self.writew_line(
                channels=dig_chan,
                time=timestep,
                address={'address' : repeat_icheck_address,
                         'special' : special_icheck,
                         'cond'    : None,
                         },
                comment=f"#Check {ivar_chan}. Go to " + \
                       f"row {repeat_icheck_address}" + \
                        ", if ivar is non-zero" + comment,
                )
        address = loop_end.first_row
        self.new_dpatt_str += self.writew_line(
                channels=dig_chan,
                time=timestep,
                address={'address' : address,
                         'special' : None,
                         'cond'    : None,
                         },
                comment=f"Go to row {address}, if ivar is zero." + comment,
                )
        count += 2
        #print("loop", count, loop_block.num_rows)

    def process_seq_logic(self, start, end):
        count = 0
        seq_len = len(start.sequence) - 1
        self.new_dpatt_str += "\n#" + start.block_id + "  " + \
                              start.sequence_name + "\n"
        for j, step in enumerate(start.sequence):
            time = step['time']
            ivar_chan = step['use_ivar']
            dig_chan = {'chan': step['chan'], 'dac': step['dac']}
            comment = step['comments']
            ivar = self.ivars[ivar_chan] if ivar_chan else None
            if ivar:
                if start.last_step_is_loop and j == seq_len:
                    time = time - self.timestep # reserve 1 timestep to point
                                                 # to next address if last loop
                                                 # in sequence block
                special_load = (1<<12) + ((2**ivar_chan)<<4)
                special_dec = (1<<12) + ((2**ivar_chan)<<8)
                special_icheck = ((12 + ivar_chan)<<12)
                if self.verbose:
                    load_comment = f"Load internal counter {ivar_chan} "
                    dec_comment = "Decrease ivar by 1"
                    check_comment = "Check ivar"
                else:
                    load_comment = ""
                    dec_comment = ""
                    check_comment = ""
                if time/self.maxtimestep/ivar/2 <= 1:
                    time_loop, load_timestep= self.timebalancer(time, ivar, 2)
                    #print(time,ivar,time_loop,load_timestep)
                    self.new_dpatt_str += self.writew_line(
                        channels=dig_chan,
                        time=load_timestep,
                        address={'address' : None,
                                 'special' : special_load,
                                 'cond'    : None,
                                },
                        comment= load_comment + comment,
                        )
                    repeat_icheck_address = self.pattern_row
                    self.new_dpatt_str += self.writew_line(
                        channels=dig_chan,
                        time=time_loop,
                        address={'address' : None,
                                 'special' : special_dec,
                                 'cond'    : None,
                                },
                        comment= dec_comment + comment,
                        )
                    self.new_dpatt_str += self.writew_line(
                        channels=dig_chan,
                        time=time_loop,
                        address={'address' : repeat_icheck_address,
                                 'special' : special_icheck,
                                 'cond'    : None,
                                },
                        comment=check_comment + comment,
                        )
                    count += 3 # For load, decrement and check
                else: # Happens at >84.8 s with max ivar(65535)
                    lines = ceil(time/self.maxtimestep/ivar)
                    time_loop, load_timestep= self.timebalancer(time, ivar,
                            lines)
                    self.new_dpatt_str += self.writew_line(
                        channels=dig_chan,
                        time=load_timestep,
                        address={'address' : None,
                                 'special' : special_load,
                                 'cond'    : None,
                                },
                        comment=load_comment + comment,
                        )
                    repeat_icheck_address = self.pattern_row
                    self.new_dpatt_str += self.writew_line(
                        channels=dig_chan,
                        time=time_loop,
                        address={'address' : None,
                                 'special' : special_dec,
                                 'cond'    : None,
                                },
                        comment=dec_comment + comment,
                        )
                    count += 2
                    for ii in range(lines-2): # minus decrement and check
                        self.new_dpatt_str += self.writew_line(
                            channels=dig_chan,
                            time=time_loop,
                            address={'address' : None,
                                     'special' : None,
                                     'cond'    : None,
                                    },
                            comment=comment,
                            )
                        count += 1
                    self.new_dpatt_str += self.writew_line(
                        channels=dig_chan,
                        time=time_loop,
                        address={'address' : repeat_icheck_address,
                                 'special' : special_icheck,
                                 'cond'    : None,
                                },
                        comment=check_comment + comment,
                        )
                    count += 1
                if start.last_step_is_loop and j == seq_len: # if last loop
                    self.new_dpatt_str += self.writew_line(
                        channels=dig_chan,
                        time=self.timestep,
                        address={'address' : end.first_row,
                                 'special' : None,
                                 'cond'    : None,
                                },
                        comment=comment,
                        )
                    count += 1
            elif ceil(time/self.maxtimestep)<1:
                address = end.first_row if j == seq_len else None
                self.new_dpatt_str += self.writew_line(
                        channels=dig_chan,
                        time=time,
                        address={'address' : address,
                                 'special' : None,
                                 'cond'    : None,
                                },
                        comment=comment,
                        )
                count += 1
            else:
                additional_rows = ceil(time/self.maxtimestep)
                if additional_rows >4:
                    warnings.warn(f"This time step uses {additional_rows} " + \
                            "rows of the pattern. Consider using ivar")
                time_left = time
                while time_left > 0:
                    if time_left > self.maxtimestep:
                        address = None
                        time_to_write = self.maxtimestep
                        time_left -= time_to_write
                    else:
                        address = end.first_row if j == seq_len else None
                        time_to_write = time_left
                        time_left -= time_to_write
                    self.new_dpatt_str += self.writew_line(
                            channels=dig_chan,
                            time=int(time_to_write),
                            address={'address' : address,
                                     'special' : None,
                                     'cond'    : None,
                                    },
                            comment=comment,
                            )
                    count += 1
        #print("sequence", count, start.num_rows)

    def timebalancer(self, time, i, looplines = 2):
        timestep = self.timestep
        load_timestep = timestep
        while ((time - load_timestep)/i/timestep%looplines):
            load_timestep += timestep
        time_loop = int((time - load_timestep)/i//looplines)
        return time_loop, load_timestep


    def process_trigger_logic(self, start, end, condition):
        ivar_needed = False
        ivar_chan = None
        #Check consistency of blocks and logic and
        # Define success and failure row address.

        if condition[1:-1] == 'success':
            test_success = end.block_id
            test_failure = start.failure
        elif condition[1:-1] == 'failure':
            test_failure = end.block_id
            test_success = start.success
        start.check_consistent(success = test_success, failure = test_failure)
        if test_success == 'loop_check':
            success_row = end.loop_check_row
        else:
            success_row = self.blocks[test_success].first_row
        if test_failure == 'loop_check':
            failure_row = end.loop_check_row
        else:
            failure_row = self.blocks[test_failure].first_row

        #Determine if ivar is needed based. We set a max of r15 lines
        if start.time_span/self.maxtimestep > 1:
            ivar_needed = True
            ivar_chan, rows = self.find_good_ivar(start.time_span, 2 )
        self.new_dpatt_str += "\n#" + start.block_id + "  " + \
                              start.trigger_name +  "\n"
        #Start writing the word
        self.trigger_write(time_span = start.time_span,
                ivar_needed = ivar_needed,
                ivar_chan = ivar_chan,
                evar_chan = start.external_input-1,
                dig_chan = {'chan': start.chan, 'dac': start.dac},
                failure_row = failure_row,
                success_row = success_row,
                num_rows = start.num_rows)
        start.written = True

    def trigger_write(self, time_span, ivar_needed, ivar_chan, evar_chan,
            dig_chan, failure_row, success_row, num_rows):
        count = 0
        if ivar_needed:
            special_load = (1<<12) + ((2**ivar_chan)<<4) + (2**evar_chan)
            special_dec = (1<<12) + ((2**ivar_chan)<<8)
            special_icheck = ((12 + ivar_chan)<<12)
            time_span_loop = time_span//self.ivars[ivar_chan]
        else:
            special_load = (1<<12) + (2**evar_chan)
            special_dec = None
        special_echeck = ((8 + evar_chan)<<12)
        special_echeck_address_failure = failure_row
        special_echeck_address_success = success_row

        # load evar
        self.new_dpatt_str += self.writew_line(
                            channels=dig_chan,
                            time=self.timestep,
                            address={'address' : None,
                                     'special' : special_load,
                                     'cond'    : None,
                                    },
                            comment='#load vars',
                            )
        count += 1
        # Time elapse via loop or single ( min 2 just to keep same num of rows)
        if ivar_needed:
            repeat_icheck_address = self.pattern_row
            self.new_dpatt_str += self.writew_line(
                            channels=dig_chan,
                            time=time_span_loop//2,
                            address={'address' : None,
                                     'special' : special_dec,
                                     'cond'    : None,
                                    },
                            comment='#Decrement internal counter',
                            )
            self.new_dpatt_str += self.writew_line(
                            channels=dig_chan,
                            time=time_span_loop//2,
                            address={'address' : repeat_icheck_address,
                                     'special' : special_icheck,
                                     'cond'    : None,
                                    },
                            comment='#Check internal counter',
                            )
            count += 2
        else:
            self.new_dpatt_str += self.writew_line(
                            channels=dig_chan,
                            time=time_span-self.timestep,
                            address={'address' : None,
                                     'special' : None,
                                     'cond'    : None,
                                    },
                            comment='',
                            )
            self.new_dpatt_str += self.writew_line(
                            channels=dig_chan,
                            time=self.timestep,
                            address={'address' : None,
                                     'special' : None,
                                     'cond'    : None,
                                    },
                            comment='',
                            )
            count += 2

        # Check evar
        self.new_dpatt_str += self.writew_line(
                            channels=dig_chan,
                            time=self.timestep,
                            address={'address' : special_echeck_address_failure,
                                     'special' : special_echeck,
                                     'cond'    : None,
                                    },
                            comment="#Check evar. Go to " + \
                            f"row {special_echeck_address_failure}" + \
                            ", if evar is non-zero(failure)",
                            )
        self.new_dpatt_str += self.writew_line(
                            channels=dig_chan,
                            time=self.timestep,
                            address={'address' : special_echeck_address_success,
                                     'special' : None,
                                     'cond'    : None,
                                    },
                            comment="#Go to row " + \
                            f"{special_echeck_address_success}" + \
                            ", if evar is zero (success)",
                            )
        count += 2
        #print("trigger", count, num_rows)

    def time_write(self, time):
        return self.w16(num=(time//self.timestep) - 1, hex=False)

    def address_write(self, address = None, special = None, cond = None):
        if cond is None:
            if special is None:
                if address is None:
                    return self.w16(self.pattern_row+1, last=True) # write the next pattern
                else:
                    return self.w16(address, last=True) # write the given address
            elif (special>>12) == 1:
                return self.w16(special, last=True) # write the special load/dec command
            else:
                return self.w16(special + address, last=True)
        else:
            raise NotImplementedError(f"Conditional not implemented yet.")
            pass

    def row_num_write(self, comment = None):
        row_str = f'\t# row {self.pattern_row}'
        if comment is not None:
            row_str += f' #{comment}'
        self.pattern_row += 1
        return row_str

    def find_good_ivar(self, span, max_lines):
        min_rows = 512
        for i, val in enumerate(self.ivars):
            rows = span/self.maxtimestep/(val+1)
            if rows < min_rows:
                min_rows = rows
                good_ivar = i
            if rows < 2:
                break
        if min_rows < max_lines:
            return good_ivar, min_rows
        else:
            warnings.warn(f"No good ivar value to use < {max_lines} rows. " +
                    f"Using ivar chan {good_ivar} with {min_rows} rows.")
            return good_ivar, min_rows

    def dig_chan_write(self, chan):
        def sum_chan_bits(chan=chan, first=0, last=15):
            return sum([2**i if i>=first and i<=last else 0 for i in chan])
        out0 = sum_chan_bits(first = 0, last = 15)
        out1 = sum_chan_bits(first = 16, last = 31) >> 16
        if self.patgen_128bit:
            out2 = sum_chan_bits(first = 32, last = 47) >> 32
            out3 = sum_chan_bits(first = 48, last = 63) >> 48
            return self.w16(out0)+self.w16(out1)+self.w16(out2)+self.w16(out3)
        return self.w16(out0)+self.w16(out1)

    def split_chan_dig_dac(self, channels):
        """
        Splits a channels dictionary into digital channel list and DAC settings dictionary.

        Args:
            channels_dict (dict): A dictionary like {'chan': [0,1], 'dac': {0:100}}.

        Returns:
            tuple: (digital_channels_list, dac_settings_dict)
        """
        return channels['chan'], channels['dac']

    def dac_config_allow(self, dac_chan):
        dac_write_allowed = True
        if self.dacconfig == 0: # All static
            if len(dac_chan)>0:
                dac_write_allowed = False
                assert dac_write_allowed, "dacconfig set to static. No write"+ \
                                          " allowed"
            else:
                dac_write_allowed = True
        elif self.dacconfig == 1: # Single 0, others static
            for i in dac_chan.keys():
                if i>0:
                    dac_write_allowed = False
                    assert dac_write_allowed, "dacconfig set to single. "+ \
                                          "Only dac 0 write allowed"
                elif i==0:
                    dac_write_allowed = True
        elif self.dacconfig == 2: # Half 0-3, others static
            for i in dac_chan.keys():
                if i>3:
                    dac_write_allowed = False
                    assert dac_write_allowed, "dacconfig set to half. "+ \
                                          "Only dac 0,1,2,3 writes allowed"
                elif i>=0 and i<4:
                    dac_write_allowed = True
        elif self.dacconfig == 4: # All variable
            for i in dac_chan.keys():
                if i>7:
                    dac_write_allowed = False
                    assert dac_write_allowed, "dacconfig set to full. "+ \
                                          "Only 0-7 DAC present"
                elif i>=0 and i<8:
                    dac_write_allowed = True
        return dac_write_allowed

    def dac_chan_write(self, dac_chan):
        assert self.patgen_128bit, "DAC not present in 64bit version"
        if len(dac_chan)==0:
            return self.w16(0) + self.w16(0) # Short circuit, 0,0 for dac
        assert self.dac_config_allow(dac_chan), "DAC channel static in config"
        first_dac_value = next(iter(dac_chan.values()))
        assert all(value == first_dac_value for value in dac_chan.values()), \
                            "Only one unique DAC value can be set per step."

        dac_value = first_dac_value
        dac_mask = 0
        for i in dac_chan.keys():
            dac_mask += 1<<i
        return self.w16(dac_value) + self.w16(dac_mask)

    def writew_line(self, channels, time, address, comment=None):
        """
        Constructs a complete 'writew' line string for the pattern file.

        Args:
            channels (dict): Dictionary with 'chan' (list of digital channels)
                             and 'dac' (dict of DAC updates).
            time (int): Time duration for this line in nanoseconds.
            address (dict or int): Address/special command.
                                   If dict: {'address': val, 'special': val, 'cond': val}.
                                   If int: direct address value.
            comment (str, optional): Comment for this line.

        Returns:
            str: The fully formatted 'writew' line string, including row number comment.
        """
        dig_chans, dac_updates = self.split_chan_dig_dac(channels)

        dig_chan_str = self.dig_chan_write(dig_chans)
        time_str = self.time_write(time) # Converts ns to hardware time value

        if isinstance(address, dict):
            address_str = self.address_write(**address)
        else: # Assuming it's a direct address integer or None
            address_str = self.address_write(address=address)

        row_num_comment_str = self.row_num_write(comment=comment)

        dac_chan_str = ""
        if self.patgen_128bit:
            dac_chan_str = self.dac_chan_write(dac_updates)

        return f"writew {dig_chan_str}{dac_chan_str}{time_str}{address_str}{row_num_comment_str}\n"

    def process_config(self):
        """
        Processes the 'control' block to set up global translator parameters
        like timestep, variable values, and hardware configuration bits.
        """
        control_block = self.blocks.get('control')
        if not control_block:
            raise ValueError("A 'control' block is required but not found.")

        self.timestep = control_block.timestep # Base hardware timestep in ns
        self.maxtimestep = self.timestep * 65536 # Max duration of a single pattern line
        self.ivars = control_block.ivars # Initial values for internal variables
        self.evars = control_block.evars # Initial values for external variables

        self.config_bits = 0 # Reset global config bits

        if control_block.patgen_128bit:
            self.patgen_128bit = True
            self.dacconfig = control_block.dacconfig # DAC mode (0-3)
            self.config_bits |= (self.dacconfig << 11)  # Bits 12:11 for DAC config
            self.config_bits |= (control_block.auxline_pol << 10) # Bit 10 for AuxOut polarity
            # Parameter register for 128-bit: startAddr, intThreshold, evars[4], ivars[4], dacs[8]
            self.param_register = [control_block.start_address, control_block.inthreshold,
                                  *control_block.evars, *control_block.ivars, *control_block.dacs]
        else:
            self.patgen_128bit = False
            # Parameter register for 64-bit: startAddr, evars[4], ivars[4]
            # (inthreshold and dacs are not applicable or handled differently)
            self.param_register = [control_block.start_address, # Assuming inthreshold is not in 64b params
                                  *control_block.evars, *control_block.ivars]


        self.config_bits |= (control_block.clock_select << 6) # Bits 7:6 for Clock Select
        self.config_bits |= (control_block.auxconfig << 4)    # Bits 5:4 for AuxOut Config
        self.config_bits |= (control_block.level << 1)        # Bit 1 for Input Level (NIM/TTL)


    def write_config(self, other_hardware_config_flags=0):
        """
        Writes the 'config' line to the .dpatt string.

        Combines configuration derived from the 'control' block with other
        hardware-specific flags.

        Args:
            other_hardware_config_flags (int): Additional hardware config bits
                                               (e.g., for table hooks, RAM target).
        """
        # Bit definitions for other_hardware_config_flags (example values from original):
        # PARAMETERWRITE = 8 (Bit 3: target RAM for writew is Params, else Pattern)
        # ADDRESSRESET = 4   (Bit 2: reset address on jumps)
        # TABLERESET = 1     (Bit 0: reset table pointer)
        # Bits 9:8 for table hooks are not explicitly set here, assumed 0 or part of other_flags.

        final_config_bits = self.config_bits | other_hardware_config_flags
        self.dpatt_str += "config " + self.w16(final_config_bits, last=True) + "\n"

    def write_param(self):
        """
        Writes the initial parameter values to the .dpatt string using 'writew'.
        These are loaded into the hardware's parameter RAM.
        """
        self.dpatt_str += "writew " # Start of the parameter write line
        num_params = len(self.param_register)
        for i, val in enumerate(self.param_register):
            is_last_param = (i == num_params - 1)
            # Parameters are typically written in decimal, regardless of global 'hex' mode.
            self.dpatt_str += self.w16(val, last=is_last_param, hex=False)
        self.dpatt_str += "\n" # End the writew line for parameters

    def w16(self, num, last=False, hex=None):
        """
        Formats a number as a 16-bit word string, optionally in hexadecimal.

        Args:
            num (int): The number to format (must be 0 <= num < 65536).
            last (bool): If True, append ';' as terminator, else ','.
            hex (bool, optional): If True, format as hex. Defaults to `self.hex`.

        Returns:
            str: The formatted 16-bit word string.

        Raises:
            AssertionError: If `num` is out of 16-bit range.
        """
        if hex is None:
            hex = self.hex # Use instance's default hex mode if not specified
        assert 0 <= num < 65536, f"Number {num} out of 16-bit range [0, 65535]."

        terminator = ";" if last else ","
        if hex:
            return f"{num:#06x}{terminator}" # Format as 0x####
        else:
            return f"{num}{terminator}"

# Example usage
if __name__ == "__main__":
    parser = configargparse.ArgumentParser(
            description="Loading of new Pattern Generator"
    )
    parser.add_argument(
            "--infile", "-i", default="example1.txt",
            help="Input file in correct syntax")
    parser.add_argument(
            "--outfile", "-o", default="example1.dpatt",
            help="Output file for DPG")
    parser.add_argument(
            "--hex", "-H", action="count", default=0,
            help="Write 16 bit words in hexadecimal, except for time word")
    parser.add_argument(
            "--verbose", "-v", action="store_true",
            help="Set verbosity of comments in output pattern file")
    args = parser.parse_args()
    filename = args.infile
    fileout = args.outfile
    verbose = args.verbose
    hex_mode = True if args.hex>0 else False
    p = MermaidParser(filename)
    p.parse()
    out = Translator(p.get_blocks(), p.get_logic(), filename, fileout, hex_mode,
            verbose)

