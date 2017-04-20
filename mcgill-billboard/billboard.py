from os.path import join
from rdflib import Graph, BNode, Namespace, RDF, RDFS, Literal, URIRef, XSD, OWL
import couchdb, re, glob

class BillboardConverter:
    def __init__(self):
        self.data_dir = "./data"
        self.salami_dir = "salami-chords"
        self.echonest_dir = "echonest"
        self.chordino = "chordino"
        self.destination = "./rdf"
        self.couch_server = couchdb.Server()
        self.couchdb = self.couch_server["musicbrainz_artists"]

    def run(self):
        self.processSalami()
        # self.processEchonest()
        # self.processChordino()

    def bindNamespaces(self):
        self.ns = {
            'afv': Namespace("https://w3id.org/afo/vocab/1.1#"),
            'afo': Namespace("https://w3id.org/afo/onto/1.1#"),
            'tl': Namespace("http://purl.org/NET/c4dm/timeline.owl#"),
            'event': Namespace("http://purl.org/NET/c4dm/event.owl#"),
            'mo': Namespace("http://purl.org/ontology/mo/"),
            'chord': Namespace("http://purl.org/ontology/chord/"),
            'dc': Namespace("http://purl.org/dc/elements/1.1/"),
            'foaf': Namespace("http://xmlns.com/foaf/0.1/")
        }
        for key in self.ns:
            self.graph.bind(key, self.ns[key])

    def createGraph(self):
        self.graph = Graph()
        self.bindNamespaces()

    def processSalami(self):
        for path in glob.glob(join(self.data_dir, self.salami_dir, "*")):
            with open(join(path, "salami_chords.txt")) as file_data:
                data = file_data.read()
                file_data.close()
            self.createGraph()
            self.processSalamiFile(data)
            self.graph.serialize(join(self.destination, path.split("/")[-1] + ".n3"), format="n3")

    # def processEchonest(self):
    #
    # def processChordino(self):

    def processSalamiFile(self, data):
        lines = data.split("\n")
        self.writeSalamiHeader(lines[0:4], lines[-2].split(" ")[0])
        self.writeSalamiContent(lines[5:-1])

    def writeSalamiHeader(self, lines, duration):
        track_id = BNode()
        self.graph.add(( track_id, RDF.type, self.ns['mo']['Track'] ))
        self.graph.add(( track_id, self.ns['dc']['title'], Literal(lines[0].split(":")[-1].strip()) ))
        artist_id = self.getMusicBrainzID(lines[1].split(":")[-1].strip())
        artist_name = lines[1].split(":")[-1].strip()
        self.graph.add(( artist_id, RDF.type, self.ns['mo']['MusicArtist'] ))
        self.graph.add(( artist_id, self.ns['foaf']['name'], Literal(artist_name) ))
        self.graph.add(( track_id, self.ns['foaf']['maker'], artist_id ))
        signal_id = BNode()
        self.graph.add(( signal_id, RDF.type, self.ns['mo']['Signal'] ))
        self.graph.add(( signal_id, self.ns['mo']['published_as'], track_id ))
        interval_id = BNode()
        self.graph.add(( interval_id, RDF.type, self.ns['tl']['Interval'] ))
        self.graph.add(( interval_id, self.ns['tl']['duration'], Literal(duration) ))
        self.graph.add(( signal_id, self.ns['mo']['time'], interval_id ))
        self.timeline_id = BNode()
        self.graph.add(( self.timeline_id, RDF.type, self.ns['tl']['Timeline'] ))
        self.graph.add(( interval_id, self.ns['tl']['timeline'], self.timeline_id ))
        metre_id = BNode()
        self.graph.add(( metre_id, RDF.type, self.ns['afv']['TimeSignature'] ))
        self.graph.add(( metre_id, RDFS.label, Literal(lines[2].split(":")[-1].strip()) ))
        self.graph.add(( metre_id, self.ns['event']['time'], interval_id ))
        tonic_id = BNode()
        self.graph.add(( tonic_id, RDF.type, self.ns['afv']['TonicPitch'] ))
        self.graph.add(( tonic_id, RDFS.label, Literal(lines[3].split(":")[-1].strip()) ))
        self.graph.add(( tonic_id, self.ns['event']['time'], interval_id ))

    def writeSalamiContent(self, lines):
        index = 0
        current_instr = None
        lines = [l for l in lines if not "# tonic" in l]
        for line in lines[0:-1]:
            print line
            interval_id = BNode()
            at = line.split("\t")[0]
            self.graph.add(( interval_id, RDF.type, self.ns['tl']['Interval'] ))
            self.graph.add(( interval_id, self.ns['tl']['timeline'], self.timeline_id ))
            self.graph.add(( interval_id, self.ns['tl']['at'], Literal(at) ))
            self.graph.add(( interval_id, self.ns['tl']['end'], Literal(lines[index+2].split("\t")[0]) ))
            if line.split("\t")[-1] == "silence":
                silence_id = BNode()
                self.graph.add(( silence_id, RDF.type, self.ns['afv']['SilentRegion'] ))
                self.graph.add(( silence_id, self.ns['event']['time'], interval_id ))
            if "|" in line:
                segment_id = BNode()
                prog_id = BNode()
                self.graph.add(( segment_id, RDF.type, self.ns['afv']['Segment'] ))
                self.graph.add(( segment_id, self.ns['event']['time'], interval_id ))
                self.graph.add(( prog_id, RDF.type, self.ns['afv']['ChordProgression'] ))
                self.graph.add(( segment_id, self.ns['afo']['feature'], prog_id ))
                chord_id = BNode()
                self.graph.add(( chord_id, RDF.type, self.ns['chord']['Chord'] ))
                chords = [cell for cell in line.split("|") if ":" in cell or "N" in cell]
                if ":" in chords[0]:
                    note, base = chords[0].strip().split(":")
                    self.graph.add(( chord_id, self.ns['chord']['root'], self.ns['chord']["note/"+note] ))
                else:
                    base = "noChord"
                self.graph.add(( prog_id, self.ns['afo']['first'], chord_id ))
                self.graph.add(( chord_id, self.ns['chord']['base_chord'], self.ns['chord'][base] ))
                for chord in chords[1:]:
                    prev_chord = chord_id
                    chord_id = BNode()
                    self.graph.add(( chord_id, RDF.type, self.ns['chord']['Chord'] ))
                    if ":" in chord:
                        note, base = chord.strip().split(":")
                        self.graph.add(( chord_id, self.ns['chord']['root'], self.ns['chord']["note/"+note] ))
                    else:
                        base = "noChord"
                    self.graph.add(( prev_chord, self.ns['afo']['next'], chord_id ))
                    self.graph.add(( chord_id, self.ns['chord']['base_chord'], self.ns['chord'][base] ))
                m = re.search(r'\t[A-Z],', line)
                if not m is None:
                    self.graph.add(( segment_id, RDFS.label, Literal(line[m.start()+1]) ))
                    section_label = line[m.start()+4:line.find(",", m.start()+3)]
                    self.graph.add(( segment_id, RDFS.label, Literal(section_label) ))
                instr = line.split(",")[-1]
                if instr.find("(") > -1 and instr.find(")") == -1:
                    if not current_instr is None:
                        self.addInstrSegment(current_instr, lines[instr_start+1].split("\t")[0], line.split("\t")[0])
                    current_instr = instr[2:]
                    instr_start = index + 1
                if instr.find(")") > -1 and instr.find("(") == -1:
                    self.addInstrSegment(current_instr, lines[instr_start].split("\t")[0], lines[index + 1].split("\t")[0])
                if instr.find("(") > -1 and instr.find(")") > -1:
                    self.graph.add(( segment_id, RDFS.label, Literal(line.split(",")[-1][2:-1]) ))
                index += 1

    def addInstrSegment(self, label, at, end):
        interval_id = BNode()
        segment_id = BNode()
        self.graph.add(( segment_id, RDF.type, self.ns['afv']['Segment'] ))
        self.graph.add(( segment_id, RDFS.label, Literal(label) ))
        self.graph.add(( interval_id, RDF.type, self.ns['tl']['Interval'] ))
        self.graph.add(( interval_id, self.ns['tl']['timeline'], self.timeline_id ))
        self.graph.add(( interval_id, self.ns['tl']['at'], Literal(at) ))
        self.graph.add(( interval_id, self.ns['tl']['end'], Literal(end) ))
        self.graph.add(( segment_id, self.ns['event']['time'], interval_id ))

    def getMusicBrainzID(self, artist_name):
        res = self.couchdb.view('views/artist_mbid_by_name', key=artist_name)
        if sum([ 1 for x in res]) == 1:
            return res.rows[0].value
        else:
            return BNode()


def main():
    BillboardConverter().run()

if __name__ == "__main__":
    main()
