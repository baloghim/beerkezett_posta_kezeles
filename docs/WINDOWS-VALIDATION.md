# Windows és hálózati átvételi próba

Éles bevezetés előtt elsőként a tényleges Windows 10 1607 x64 (build 14393) célgépen, kizárólag külön tesztmegosztással végezze el. Valós hivatali dokumentumokat ne másoljon a tesztkörnyezetbe.

A [1607-es EXE-önellenőrzést](WINDOWS1607.md) futtassa le a részletes próba előtt. A modern CI runner eredménye nem helyettesíti ezt.

1. A teljes kiadási ZIP kibontása után indítsa az `EDPD-Manager.exe` fájlt olyan gépen is, ahol nincs Python. Ellenőrizze a Qt-pluginok betöltését.
2. Adjon meg két külön tesztmappát. Próbáljon meghajtóbetűjelet, UNC-útvonalat, ékezetes neveket, mappahivatkozást és ugyanannak a mappának különböző elérési útjait. Az azonos és egymásba ágyazott forrás/cél beállítást a programnak el kell utasítania.
3. Helyezzen több ZIP-et azonos dátummal a forrásba, PDF- és CSV-bejegyzésekkel. Ellenőrizze a csoportosítást, a ZIP-ből megtekintést és a három alapállapotot.
4. Próbálja a kihagyást, a tudatos felülírást, a napi törlést és a teljes ürítést. A forrásfájlok és a cél egyéb állományai maradjanak érintetlenek.
5. Két külön gépről egyszerre indítson nagyobb kicsomagolást. Egyetlen gép módosíthassa a munkamappát. Leállított kliens után a szervernek fel kell oldania a fájlzárat; hálózati kimaradáskor ennek ideje az SMB-kiszolgálótól függ. A `.edpd-operation.lock` fájlt ne törölje.
6. Olvasás és írás közben kapcsolja le a tesztmegosztást. Legyen érthető hiba; felülírási hiba esetén a korábbi cél-PDF maradjon ép. A már elkészült fájlok megmaradnak: a napi művelet fájlonként atomikus, nem teljes napi tranzakció.
7. A ZIP-ből és a célból megnyitott többoldalas, vegyes tájolású PDF-et nyomtassa Microsoft Print to PDF-re és fizikai nyomtatóra. Vizsgálja az oldalintervallumot, példányszámot, fordított sorrendet, margókat és minden oldal teljes tartalmát. A párbeszéd megszakítása ne indítson nyomtatást.
8. Ellenőrizze a 14/30/90/180 napos és Összes nézetet. Régi munkamappabeli PDF-et és ismeretlen dokumentumot is hagyjon a célban; a már ismert forrásnap az indexből jelenjen meg, ismeretlennél ne induljon automatikus régi ZIP-keresés. A További forráskeresés gombbal külön kérhető a feltérképezés; ütközésnél Több lehetséges nap jelzés szükséges. A felső nap kijelölése ne szűrje az alsó listát és ne váltson PDF-et.
9. Kicsomagoláskor ellenőrizze az üres, részleges és teljes napi állapotot; a dupla kattintás csak egyszer indítson műveletet. Két klienssel próbálja a zárat és az időközben megváltozott célfájl miatti új felülírási megerősítést. A folyamatjelző valós fájlszámot mutasson, a PDF-betekintő közben működjön.
10. Ellenőrizze 5 és 60 perces frissítéssel, hogy az olvasott PDF nyitva marad. Indítsa újra az alkalmazást, ellenőrizze a beállítások és ablakelrendezés megmaradását.

## Ismert működési határok

- Egy PDF legfeljebb 256 MiB, egy napi adag legfeljebb 2 GiB. Titkosított ZIP/PDF nem támogatott.
- A státusz fájlnév és méret alapján készül, nem hitelességvizsgálat. Az azonos méretű, külső program által módosított PDF nem feltétlenül ismerhető fel. A napi csomagok közötti névütközést CRC és méret alapján külön ellenőrizzük.
- Más alkalmazások nem tartják tiszteletben az EDPD fájlzárát. Az EDPD-műveletek idején ne módosítsák a célmappát külső fájlkezelővel.
- A program nem szakítja félbe erőszakkal az operációs rendszer hálózati hívásait; hálózati kieséskor az OS-időtúllépésig a feladat várakozhat. A felület használható, bezárni a háttérfeladat befejezése után lehet.
- A normál és hibával visszatérő fájlműveletek takarítják a saját ideiglenes fájlt. Áramkimaradás vagy folyamatkilövés után `.edpd-*.tmp` maradhat a célban. Ezek dokumentumadatot tartalmazhatnak; az üzemeltető csak minden kliens leállítása után távolítsa el őket. A program nem töröl automatikusan technikai állományokat.
- Windows EXE-t Linuxon nem készítünk; a Windows Actions futás és a fenti kézi ellenőrzés külön bizonyíték szükséges a kiadáshoz.
