from os.path import join
from rdflib import Graph, BNode, Namespace, RDF, RDFS, Literal, URIRef, XSD, OWL
import glob, wave

class Adc2004Converter:
    def __init__(self):
        self.data_dir = "./data"
        self.destination = "./rdf"

    def run(self):
        for path in glob.glob(self.data_dir + "/*REF.txt"):
            self.createGraph()
            with open(path, "r") as adc_file:
                data = adc_file.read()
                adc_file.close()
            audio_data = self.get_audio_data(path.replace("REF.txt", ".wav"))
            self.convert(data, audio_data)
            write_path = self.destination + "/" + path.split("/")[-1].split(".")[0] + ".n3"
            self.graph.serialize(write_path, format="n3")

    def bindNamespaces(self):
        self.ns = {
            'afv': Namespace("https://w3id.org/afo/vocab/1.1#"),
            'afo': Namespace("https://w3id.org/afo/onto/1.1#"),
            'tl': Namespace("http://purl.org/NET/c4dm/timeline.owl#"),
            'event': Namespace("http://purl.org/NET/c4dm/event.owl#"),
            'mo': Namespace("http://purl.org/ontology/mo/"),
            'sxsd': Namespace("https://www.w3.org/TR/speech-synthesis11/synthesis-nonamespace.xsd#")
        }
        for key in self.ns:
            self.graph.bind(key, self.ns[key])

    def createGraph(self):
        self.graph = Graph()
        self.bindNamespaces()

    def convert(self, data, audio_data):
        self.signal = BNode()
        self.file = URIRef(audio_data['path'].split("/")[-1])
        self.timeline = BNode()
        self.interval = BNode()
        duration = audio_data['n_frames'] / audio_data['f_rate']

        self.graph.add(( self.signal, RDF.type, self.ns['mo']['Signal'] ))
        self.graph.add(( self.file, RDF.type, self.ns['mo']['AudioFile'] ))
        self.graph.add(( self.timeline, RDF.type, self.ns['mo']['Timeline'] ))
        self.graph.add(( self.interval, RDF.type, self.ns['tl']['Interval'] ))
        self.graph.add(( self.file, self.ns['mo']['encodes'], self.signal ))
        self.graph.add(( self.signal, self.ns['mo']['sample_rate'], Literal(audio_data['f_rate']) ))
        self.graph.add(( self.signal, self.ns['mo']['channels'], Literal(audio_data['n_channels']) ))
        self.graph.add(( self.signal, self.ns['mo']['time'], self.interval ))
        self.graph.add(( self.interval, self.ns['tl']['duration'], Literal(str(duration), datatype=XSD.duration) ))
        self.graph.add(( self.interval, self.ns['tl']['timeline'], self.timeline ))

        index = 0
        for row in data.split("\n"):
            if row != "":
                time, freq = row.split("     ")
                event_id = BNode("event_" + str(index))
                interval_id = BNode()
                self.graph.add(( event_id, RDF.type, self.ns['afv']['FundamentalFrequency'] ))
                self.graph.add(( event_id, self.ns['afo']['value'], Literal(str(float(freq)), datatype=self.ns['sxsd']['hertz.number']) ))
                self.graph.add(( event_id, self.ns['event']['time'], interval_id ))
                self.graph.add(( interval_id, self.ns['tl']['at'], Literal(time, datatype=XSD.float) ))
                self.graph.add(( interval_id, self.ns['tl']['duration'], Literal((256.0/44100.0), datatype=XSD.duration) ))
                self.graph.add(( interval_id, self.ns['tl']['timeline'], self.timeline ))
                index += 1

    def get_audio_data(self, path):
        audio_data = {}
        wave_read = wave.open(path, 'rb')
        audio_data['n_channels'] = wave_read.getnchannels()
        audio_data['n_frames'] = wave_read.getnframes()
        audio_data['s_width']= wave_read.getsampwidth()
        audio_data['f_rate'] = wave_read.getframerate()
        audio_data['path'] = path
        wave_read.close()
        return audio_data

def main():
    Adc2004Converter().run()

if __name__ == "__main__":
    main()
