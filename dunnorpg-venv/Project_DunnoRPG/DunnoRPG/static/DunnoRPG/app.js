
//Still in need to ignore values set by races(for example if race has -1 of int it doesn't take point when changed to 0)
class CharacterCreation{
    constructor() {}
    pointsToUse=10;
    races(){
        const race = document.getElementById('id_race')
        const int = document.getElementById('id_INT')
        const sil = document.getElementById('id_SIŁ')
        const zre = document.getElementById('id_ZRE')
        const char = document.getElementById('id_CHAR')
        const cel = document.getElementById('id_CEL')
    
        const raceAttributes = {
            'Athel Loren Elven': { int: -1, sil: 0, zre: 0, char: 0, cel: 0, p: 10 },
            'Halfling': { int: 0, sil: -2, zre: 0, char: 0, cel: 0, p: 10 },
            'Gnome': { int: 0, sil: -2, zre: 0, char: 0, cel: 0, p: 10 },
            'Half-orc': { int: -2, sil: 1, zre: -1, char: 0, cel: 0, p: 10 },
            'Half-elf': { int: 0, sil: -1, zre: 0, char: 0, cel: 0, p: 10 },
            'Ogre': { int: -1, sil: 3, zre: -3, char: 0, cel: 0, p: 10 },
            'Satyr': { int: -1, sil: 0, zre: 1, char: -1, cel: 0, p: 10 },
            'High Elven (Asurii)': { int: 0, sil: -1, zre: 0, char: -2, cel: 0, p: 10 },
            'Orc': { int: -3, sil: 2, zre: -2, char: 0, cel: 0, p: 10 },
            'Goblin': { int: 0, sil: -1, zre: 1, char: 0, cel: 0, p: 10 },
            'Dwarf': { int: 0, sil: -1, zre: 0, char: -2, cel: 0, p: 10 },
            'Human(Kislev)': { int: 0, sil: 0, zre: 0, char: 1, cel: 0, p: 10 },
            'Human(Empire)': { int: 0, sil: 0, zre: 0, char: 0, cel: 0, p: 11 },
            'Human(Bretonnia)': { int: 0, sil: 0, zre: 0, char: 0, cel: 0, p: 10 },
            'Vampire': { int: 0, sil: 0, zre: 0, char: 0, cel: 0, p: 10 },
          }
    
        race.addEventListener("change", function() {
            const selectedRace = race.value;
            const attributes = raceAttributes[selectedRace];
            int.value = attributes.int;
            sil.value = attributes.sil;
            zre.value = attributes.zre;
            char.value = attributes.char;
            cel.value = attributes.cel;
            this.pointsToUse = attributes.p;
            document.getElementById('points_left').innerHTML = this.pointsToUse
          });
    
    }

    count_points() {
        const fields = document.querySelectorAll("input[type='number']");
        const int = parseInt(document.getElementById('id_INT').value)
        const sil = parseInt(document.getElementById('id_SIŁ').value)
        const zre = parseInt(document.getElementById('id_ZRE').value)
        const char = parseInt(document.getElementById('id_CHAR').value)
        const cel = parseInt(document.getElementById('id_CEL').value)
        let pointsLeft = document.getElementById('points_left')
        let pointsArray = [0,0,0,0,0]
    
        for (let i = 0; i < fields.length; i++) {
            fields[i].addEventListener("input", () => {
                if (fields[i].value !== '') {
                    pointsArray[i] = parseInt(fields[i].value)
                    let pointsUsed = pointsArray.reduce((a, b) => {
                            return a + b;
                          })
                    console.log(pointsArray, pointsUsed)
                    pointsLeft.innerHTML = this.pointsToUse - pointsUsed
                }
            });
          }
    }
}