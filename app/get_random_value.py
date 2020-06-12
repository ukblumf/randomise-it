from .randomise_utils import get_random_table_record, get_macro_record
import random
import re


def get_row_from_external_table(close_angle_brackets, external_id, open_angle_brackets, selected_text):
    external_text = 'Problem with ' + external_id
    username, id_type, ident = external_id.split('.')

    if id_type == 'table':
        table = get_random_table_record(username, ident)
        if table is not None:
            external_text = get_row_from_random_table_definition(table)
        else:
            external_text = 'error reading from ' + external_id

    if id_type == 'macro':
        macro = get_macro_record(username, ident)
        if macro is not None:
            external_text = process_text(macro.definition)
        else:
            external_text = 'error reading from ' + external_id

    selected_text = selected_text[:open_angle_brackets] + external_text + selected_text[close_angle_brackets + 2:]
    return selected_text


def get_row_from_random_table_definition(table):
    min_rng = table.min
    max_rng = table.max
    table_list = table.definition.splitlines()
    table_iter = iter(table_list)
    random_number = random.randint(min_rng, max_rng)
    selected_text = ''
    # get row from table
    if table.line_type == 1:
        for i in table_iter:
            line_def = i.split('::')
            if bool(re.search(r'^\d+-\d+$', line_def[0])):
                match_values = re.search(r'^(\d+)-(\d+)$', line_def[0])
                if int(match_values.group(1)) <= random_number <= int(match_values.group(2)):
                    selected_text = line_def[1]
                    break
            else:
                if int(line_def[0]) == random_number:
                    selected_text = line_def[1]
                    break
    else:
        selected_text = table_list[random_number - 1]

    return process_text(selected_text)


def process_text(text):
    open_brackets = text.find("((")  # find first set of double open brackets
    while open_brackets >= 0:
        close_brackets = text.find("))", open_brackets)  # find matching closing double brackets
        generator = text[open_brackets + 2:close_brackets]  # extract generator
        generated_text = ''
        value = 0
        # what type of generator
        if bool(re.search(r'^\d+d\d+$', generator, re.IGNORECASE)):
            # Found dice type random number
            dice = re.search(r'^(\d+)d(\d+)$', generator, re.IGNORECASE)
            # Comprising number of dice in dice.group(1))
            # And dice size in dice.group(2))
            for d in range(int(dice.group(1))):
                value += random.randint(1, int(dice.group(2)))
            generated_text = str(value)

        elif bool(re.search(r'^\d+d\d+x\d+$', generator, re.IGNORECASE)):
            # Found dice type random number with multiplier
            dice = re.search(r'^(\d+)d(\d+)', generator, re.IGNORECASE)
            multiplier = re.search(r'x(\d+)$', generator, re.IGNORECASE)
            # Number of dice in dice.group(1))
            # Dice size in dice.group(2))
            # Multiplier in multiplier.group(1))
            for d in range(int(dice.group(1))):
                value += random.randint(1, int(dice.group(2)))
            value *= int(multiplier.group(1))
            generated_text = str(value)

        elif bool(re.search(r'^\d+d\d+\+\d+$', generator, re.IGNORECASE)):
            # Found dice type random number with addition
            dice = re.search(r'^(\d+)d(\d+)', generator, re.IGNORECASE)
            addend = re.search(r'\+(\d+)$', generator, re.IGNORECASE)
            # Number of dice in dice.group(1))
            # Dice size in dice.group(2))
            # Added number in multiplier.group(1))
            for d in range(int(dice.group(1))):
                value += random.randint(1, int(dice.group(2)))
            value += int(addend.group(1))
            generated_text = str(value)

        elif bool(re.search(r'^\d+d\d+\-\d+$', generator, re.IGNORECASE)):
            # Found dice type random number with subtraction
            dice = re.search(r'^(\d+)d(\d+)', generator, re.IGNORECASE)
            subtraend = re.search(r'\-(\d+)$', generator, re.IGNORECASE)
            # Number of dice in dice.group(1))
            # Dice size in dice.group(2))
            # Added number in multiplier.group(1))
            for d in range(int(dice.group(1))):
                value += random.randint(1, int(dice.group(2)))
            value += int(subtraend.group(1))
            generated_text = str(value)

        elif bool(re.search(r'^\d+-\d+$', generator, re.IGNORECASE)):
            # Found range type random number
            rng = re.search(r'^(\d+)-(\d+)$', generator, re.IGNORECASE)
            # Min range in rng.group(1))
            # Max range in rng.group(2))
            value = random.randint(int(rng.group(1)), int(rng.group(2)))
            generated_text = str(value)

        elif bool(re.search(r'^\d+-\d+x\d+$', generator, re.IGNORECASE)):
            # Found range type random number with multiplier
            rng = re.search(r'^(\d+)-(\d+)', generator, re.IGNORECASE)
            multiplier = re.search(r'x(\d+)$', generator, re.IGNORECASE)
            # Min range in rng.group(1)
            # Max range in rng.group(2))
            # Multiplier in multiplier.group(1))
            value = random.randint(int(rng.group(1)), int(rng.group(2)))
            value *= int(multiplier.group(1))
            generated_text = str(value)

        elif bool(re.search(r'^\d+d\d+x<<.*?>>$', generator, re.IGNORECASE)):
            # found dice type random number with external reference
            dice = re.search(r'^(\d+)d(\d+)', generator, re.IGNORECASE)
            external_table = re.search(r'x<<(.*?)>>$', generator, re.IGNORECASE)
            # number of dice IN dice.group(1)
            # dice size IN dice.group(2)
            # external table in external_table.group(1)
            for d in range(int(dice.group(1))):
                roll = random.randint(1, int(dice.group(2)))
                for n in range(roll):
                    generated_text += get_row_from_external_table(0, external_table.group(1), 0, "") + ", "

        elif bool(re.search(r'^\d+-\d+x<<.*?>>$', generator, re.IGNORECASE)):
            # Found range type random number with external reference
            rng = re.search(r'^(\d+)-(\d+)', generator, re.IGNORECASE)
            # Min range in rng.group(1))
            # Max range in rng.group(2))
            external_table = re.search(r'x<<(.*?)>>$', generator, re.IGNORECASE)
            # External table in external_table.group(1))
            roll = random.randint(int(rng.group(1)), int(rng.group(2)))
            for n in range(roll):
                generated_text += get_row_from_external_table(0, external_table.group(1), 0, "") + ","

        elif bool(re.search(r'(\d+d\d+|\d+|[\+|\-])', generator, re.IGNORECASE)):
            # found chained dice and static numbers to produce sum
            components = re.finditer(r'(\d+d\d+|\d+|[\+|\-])', generator, re.IGNORECASE)
            result = 0
            expect_value = True
            operand = 1
            for component in components:
                if expect_value:
                    expect_value = False
                    if re.search(r'd', component.group(1), re.IGNORECASE):
                        # dice notation
                        dice = re.search(r'^(\d+)d(\d+)', component.group(1), re.IGNORECASE)
                        for d in range(int(dice.group(1))):
                            result += (random.randint(1, int(dice.group(2))) * operand)
                    elif re.search(r'\d+', component.group(1), re.IGNORECASE):
                        # static number
                        result += (int(component.group(1)) * operand)
                else:
                    expect_value = True
                    if component.group(1) == '+':
                        operand = 1
                    elif component.group(1) == '-':
                        operand = -1

            generated_text = str(result)

        text = text[:open_brackets] + generated_text.rstrip(' ').rstrip(',') + text[close_brackets + 2:]
        open_brackets = text.find("((", open_brackets)

    open_angle_brackets = text.find("<<")
    while open_angle_brackets >= 0:
        close_angle_brackets = text.find(">>", open_angle_brackets)
        external_id = text[open_angle_brackets + 2:close_angle_brackets]
        # Found external id in external_id)
        # check if chance
        if bool(re.search(r'^\d+%\s', external_id)):
            chance = re.search(r'^(^\d+)%\s(.*)$', external_id)
            # Found chance in chance.group(1))
            if random.randint(1, 100) <= int(chance.group(1)):
                # Chance succeeded
                external_id = chance.group(2)
            else:
                text = text[:open_angle_brackets] + text[close_angle_brackets + 2:]
                open_angle_brackets = text.find("<<", open_angle_brackets)
                # current_app.logger.warning('open angle brackets ' + str(open_angle_brackets) + ', ' + text)
                continue

        text = get_row_from_external_table(close_angle_brackets, external_id, open_angle_brackets, text)
        open_angle_brackets = text.find("<<", open_angle_brackets)
    return text
