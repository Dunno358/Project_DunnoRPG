
//Still in need to ignore values set by races(for example if race has -1 of int it doesn't take point when changed to 0)
class CharacterCreation{
    constructor() {}
    static pointsToUse = 10
    races(){
        const race = document.getElementById('id_race')
        const int = document.getElementsByTagName('label')[2]
        const sil = document.getElementsByTagName('label')[3]
        const zre = document.getElementsByTagName('label')[4]
        const char = document.getElementsByTagName('label')[5]
        const cel = document.getElementsByTagName('label')[6]
        //const int = document.getElementById('id_INT')
        //const sil = document.getElementById('id_SIŁ')
        //const zre = document.getElementById('id_ZRE')
        //const char = document.getElementById('id_CHAR')
        //const cel = document.getElementById('id_CEL')
        console.log(document.getElementsByTagName('label'))
    
        const raceAttributes = {
            'Leśne Elfy (Athel Loren)': { int: '-1', sil: '+0', zre: '+2', char: '-2', cel: '+1', p: 10 },
            'Niziołek': { int: '+0', sil: '-2', zre: '+3', char: '-1', cel: '+0', p: 10 },
            'Gnom': { int: '+0', sil: '-2', zre: '+2', char: '+0', cel: '+0', p: 10 },
            'Półork': { int: '-2', sil: '+2', zre: '+2', char: '-2', cel: '+0', p: 10 },
            'Półelf': { int: '+0', sil: '-1', zre: '+1', char: '-1', cel: '+1', p: 10 },
            'Ogr': { int: '-2', sil: '+4', zre: '-2', char: '+0', cel: '+0', p: 10 },
            'Satyr': { int: '0', sil: '+1', zre: '+1', char: '-2', cel: '+1', p: 10 },
            'Wysokie Elfy (Asurii)': { int: '+0', sil: '-1', zre: '+1', char: '-3', cel: '+2', p: 10 },
            'Ork': { int: '-3', sil: '+3', zre: '-1', char: '+0', cel: '+0', p: 10 },
            'Goblin': { int: '+1', sil: '-2', zre: '+1', char: '+0', cel: '+0', p: 10 },
            'Krasnolud': { int: '+1', sil: '-0', zre: '-2', char: '+0', cel: '+1', p: 10 },
            'Człowiek(Kislev)': { int: '-2', sil: '+1', zre: '+0', char: '+1', cel: '+0', p: 10 },
            'Człowiek(Imperium)': { int: '+1', sil: '+0', zre: '+0', char: '+0', cel: '+0', p: 11 },
            'Człowiek(Bretonnia)': { int: '-2', sil: '+1', zre: '+1', char: '+0', cel: '+0', p: 10 },
            'Wampir': { int: '+1', sil: '-1', zre: '+0', char: '+0', cel: '+0', p: 10 },
          }
    
        race.addEventListener("change", function() {
            int.innerHTML = "INT:";
            sil.innerHTML = "SIŁ:";
            zre.innerHTML = "ZRE:";
            char.innerHTML = "CHAR:";
            cel.innerHTML = "CEL:";

            const selectedRace = race.value;
            const attributes = raceAttributes[selectedRace];
            console.log(attributes.int)
            int.innerHTML = "("+attributes.int+") "+int.innerHTML;
            sil.innerHTML = "("+attributes.sil+") "+sil.innerHTML;
            zre.innerHTML = "("+attributes.zre+") "+zre.innerHTML;
            char.innerHTML = "("+attributes.char+") "+char.innerHTML;
            cel.innerHTML = "("+attributes.cel+") "+cel.innerHTML;
            CharacterCreation.pointsToUse = attributes.p;
            document.getElementById('points_left').innerHTML = CharacterCreation.pointsToUse
          });
    
    }

    count_points(){
        const fields = document.querySelectorAll("input[type='number']");
        const int = parseInt(document.getElementById('id_INT').value)
        const sil = parseInt(document.getElementById('id_SIŁ').value)
        const zre = parseInt(document.getElementById('id_ZRE').value)
        const char = parseInt(document.getElementById('id_CHAR').value)
        const cel = parseInt(document.getElementById('id_CEL').value)
        let pointsLeft = document.getElementById('points_left')
        let pointsArray = [0,0,0,0,0]
        //console.log(document.getElementsByTagName('label'))
    
        for (let i = 0; i < fields.length; i++) {
            fields[i].addEventListener("input", () => {
                if (fields[i].value !== '') {
                    pointsArray[i] = parseInt(fields[i].value)
                    let pointsUsed = pointsArray.reduce((a, b) => {
                            return a + b;
                          })
                    console.log(CharacterCreation.pointsToUse,pointsUsed)
                    pointsLeft.innerHTML = CharacterCreation.pointsToUse - pointsUsed
                }
            });
          }
    }
}