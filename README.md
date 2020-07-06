The Randomist
============

The ability to create, store, edit and share random tables, macros and collections

Develop a standard way to create random tables and reference other random tables that is easy to use.

Provide an easy scripting language to tie together multiple random tables to produce a paragraph or formatted text.

## Defining a Random Table

Random tables will be defined by a header/title line, optional description a unique (to the user) identifier  
The unique identifier can only comprise of lowercase letters, numbers and '_', '-'

The rows of the table are split into two columns, the first column represents the value(s) needed to select that particular row, the second column is the text, It will be separated by double colon, i.e. `~::



### Example random table
TITLE: What Happens  
ID: what-happens  
DESCRIPTION: some optional description
```
1::Something bad happens
2-5::Nothing happens
6::Something good happens
```
The import of the random table list will work out the upper and lower range of values that need to be generated, in the case above. This will be a random value between 1 and 6.

You can also leave numbers out entirely and get the random selection to pick just from the rows in the table

TITLE: What Happens When no Numbers.  
ID: what-happens-when-no-numbers
```
This could happen
But also this could happen
I could happen
```

You can't mix rows with or without numbers, rows either have no numbers or all numbers.

### Referencing other lists
Often random lists need to refer to other lists, this is down via surrounding the list identifier with << and >>
Here is an example of random table referring to table defined above.

#### Example
TITLE: More Happens  
ID: more-happens  
DESCRIPTION: some optional description
```
1::<<username.table.what-happens>> followed by <<username.table.what-happens>>
2::Happy happenstance
3::Whilst you sleep <<username.macro.what-happens>>
```
In the above example the more-happens table is referencing the what-happens table.
Note that the reference id between << >> follows the form username.type.id  


### Generating random numbers
To generate a random number to include in text surround range with double brackets, a range can be specified with a dash or in dice notation. Multiplications are possible in initial version.

TITLE: Keeps Happening
ID: keeps-happening
E.g.
```
1::Something keeps happening ((1-10)) times during night
2::You find ((3d6)) things
3::The next day ((1d20)) <<username.table.what-happens>>  occur.
4::((1-100)) kobolds carrying ((1d8))) copper pieces each, appear!
5::You find ((3d6x100)) gold pieces, you lucky thing.
```

### Generator types
There are many types of number generators, here is current complete list.
```
((<number of dice>d<die type>)), e.g. 2d4, 3d6, 1d20
((<low range>-<high range>)), e.g 1-10, 13-24, 1-100
((<number of dice>d<die type>x<multiplier>)), e.g. 3d6x10, 1d12x100
((<number of dice>d<die type>+<add>)), e.g. 2d4+2, 3d6+4
((<number of dice>d<die type>-<subtract>)), e.g. 4d4-1, 3d6-2
((<low range>-<high range>x<multiplier>)), e.g. 1-10x100, 3-18x10
((<number of dice>d<die type>x<<external table/macro>>)), e.g   2d4x<<user.table.randomtable>>
                                                                3d6x<<user.macro.randommacro>>
((<low range>-<high range>x<<external table/macro>>)), e.g      1-10x<<user.table.randomtable>>
                                                                2-4x<<user.macro.randommacro>>
((dice chain)), e.g 1d6+1d4+1, 3d6+2d8-2, 6+1d6+1d8-2
```


### Sharing
Lists can be private, public or commercial.

**Private**, only can be seen by yourself.

**Public**, allows anyone to use your list but can only use resulting values they cannot see list.

**Commercial** - COMING SOON - allows other users to purchase your list but only use resulting values cannot see list.

Other sharing options will be Viewable data, allowing other users to see contents of list and Editable lists to allow other 
users to edit their own copy of table, macro or collection.

### Macros
Macros produce a paragraph or sentence based upon connecting multiple random tables (or even other macros) together.

```
##Introduction
<<table.introduction>>
Along the way <<myuser.table.1372-roadside-encounters>> 
The dungeon is located <<myuser.table.dungeon-location>> 
It was created by <<myuser.table.dungeon-creator>> 
The party goal is <<myuser.table.dungeon-goals>>
The adventure ends with <<myuser.table.climax>>
```

### Collections
Collated list of tables and macros to form a menu, other collections can be added which form a sub-menu.
The collection is primarily used in creating stories, they can be pinned to form drop-down menus which enable quick
selection of items.

### Story creator
This is where the power of the random tables, macros and collections come into action, a markdown compatible textbox which allows inserting items from any accessible random list, either by a single click or  hot-key for commonly used random items.

Macros can be fired to insert into story at any point, just like a single item from a list. All fully editable if a better idea springs to mind.

Never get stuck whilst writing an idea, using random lists to generate anything from names, places, locations, encounters, anything. Kick starting whole new wholly original ideas from the seeds provided.





