
Aktualizace pip:
```bash
pip install --upgrade pip
```

Instalation of pip dependencies with system package manager compatibility:
```bash
mkdir -p ~/.config/pip
cat > ~/.config/pip/pip.conf <<'EOF'
[global]
break-system-packages = true
EOF
pip install --upgrade pip
```

Nebo dočasně nastavit proměnnou prostředí PIP_BREAK_SYSTEM_PACKAGES na true:
```bash
export PIP_BREAK_SYSTEM_PACKAGES=true
```

Dočasné přidání do path:
```bash
export PATH="$HOME/.local/bin:$PATH"
```

<!--
    type: item | ability | coin
    class: (optional) mage | warrior | paladin | hunter | thief
    school: (optional) attack | defense | spell | utility
    slot: (optional) one_hand | two_hand | shield | armor | head | ring | necklace
    cost: integer
    value: (optional) same as cost (pro budoucí)
    tags: comma-separated (optional)
-->

Jak by to vypadalo v XML
Máš dva soubory:

* cards/*.xml – data karet
* config/layout.xml – definice layoutů pro jednotlivé typy (loot/monster/…)

layout.xml (příklad)

```xml
<layouts>
  <layout for="loot">
    <field key="icon"    area="header_left"/>
    <field key="name"    area="header_title"/>
    <field key="subtitle" area="header_subtitle"/>
    <field key="meta"    area="meta_line"/>
    <field key="text"    area="body"/>
    <field key="cost"    area="header_right"/>
  </layout>

  <layout for="monster">
    <field key="icon" area="header_left"/>
    <field key="name" area="header_title"/>
    <field key="stats" area="body_top"/>
    <field key="text" area="body"/>
    <field key="lootBudget" area="footer_right"/>
  </layout>
</layouts>
```

A pak renderer udělá:

* podle typu karty (loot/monster/…) vybere layout
* každé “field key” ví, odkud vzít data:

  * key="name" -> card/name
  * key="cost" -> card/loot/@cost
  * key="stats" -> spočítá z monster hp/atk/def
* area je jen “slot” (header_left/body/…), který renderer mapuje na konkrétní obdélník v PDF

Tohle je super protože:

* layout můžeš měnit bez změny kódu (nebo s minimem změn)
* XSD ti garantuje, že layout soubor je validní
* pro nový typ karty jen přidáš nový <layout for="…">

Jak to zvalidovat (XSD pro layout)
Uděláš druhé schema (layout.xsd). V něm:

* <layouts> obsahuje mnoho <layout>
* <layout @for> je enumerace: loot/biome/npc/monster/quest/curse/health
* <field @key> je enumerace: name/subtitle/text/icon/meta/cost/hp/atk/def/lootBudget/…
* <field @area> je enumerace: header_left/header_right/header_title/header_subtitle/meta_line/body/body_top/footer_left/footer_right…

Tím dostaneš formální popis “co kde má být”.
