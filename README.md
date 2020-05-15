RANDOMISE-IT
============

The ability to create, store, edit and share random tables.

Develop a standard way to create random tables and reference other random tables that is easy to use.

Provide an easy scripting language to tie together multiple random tables to produce a paragraph or formatted text.

## Defining a Random Table

Random tables will be defined by a header/title line, optional description and followed by rows.

The rows are split into two columns, the first column represents the value(s) needed to select that particular row, the second column is the text, It will be separated by double colon, i.e. `~::

The title line will also comprise of two elements, a unique identifier and a display title, separated by ::
The unique identifier can only comprise of lowercase letters, numbers and '_', '-', '.'

Optional description of list, this appears below identifier/title line and is surrounded by double colons. This can contain markdown to allow highlighting and formatting.

### Example random table
```
what-happens::What Happens
::Optional description of the list::
1::Something bad happens
2-5::Nothing happens
6::Something good happens
```
The import of the random table list will work out the upper and lower range of values that need to be generated, in the case above. This will be a random value between 1 and 6.

If the unique identifier already exists in your local lists then it will overwrite, a warning will be displayed before this happens.


### Referencing other lists
Often random lists need to refer to other lists, this is down via surrounding the list identifier with << and >>
Here is an example of random table referring to table defined above.
```
more-happenings::More Happenings
1::<<what-happens>> followed by <<what-happens>>
2::Happy happenstance
3::Whilst you sleep <<what-happens>>
```
Of course, this could quite easily cause a circular dependencies if the references were drilled down, so for the initial version a reference only works down one level.


### Generating random numbers
To generate a random number to include in text surround range with double brackets, a range can be specified with a dash or in dice notation. Multiplications are possible in initial version.

E.g.
```
keeps-happening::Keeps Happening
1::Something keeps happening ((1-10)) times during night
2::You find ((3d6)) things
3::The next day ((1d20)) <<what-happens>>  occur.
4::((1-100)) kobolds carrying ((1d8))) copper pieces each, appear!
5::You find ((3d6x100)) gold pieces, you lucky thing.
```


###List Types
Lists can be private, public or commercial.

**Private**, only can be seen by yourself.
**Public Open**, allows anyone to use your list and see contents of list
	• Possible new property - Editable Yes/No
**Public Closed**, allows anyone to use your list but can only use resulting values they cannot see whole list.
**Commercial Open**, allows other users to purchase your list and then see entire contents.
	• Possible new property - Editable Yes/No
**Commercial Closed**, allows other users to purchase your list but only use resulting values cannot see whole list.



###Macros
Macros produce a paragraph or sentence based upon connecting multiple random tables (or even other macros) together.
They have a unique identifier (same as lists), a display title, and optional description and a single markdown block, as the markdown syntax does not use << >> this enables the referencing of the lists.
To reference a public or commercial list, the referencing syntax is <<user-id.listid>> where user-id is the userid of the source originating account.
```
##Introduction
<<table.introduction>>
Along the way <<table.1372-roadside-encounters>> 
The dungeon is located <<table.dungeon-location>> 
It was created by <<table.dungeon-creator>> 
The party goal is <<table.dungeon-goals>>
The adventure ends with <<table.climax>>
```

###Story creator
This is where the power of the lists come into action, a markdown compatible textbox which allows inserting items from any accessible random list, either by a single click or  hot-key for commonly used random items.

Ramble macros can be fired to insert into story at any point, just like a single item from a list. All fully editable if a better idea springs to mind.

Never get stuck whilst writing an idea, using random lists to generate anything from names, places, locations, encounters, anything. Kick starting whole new wholly original ideas from the seeds provided.





