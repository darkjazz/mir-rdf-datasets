from hdf5_getters import *
from os.path import join
from rdflib import Graph, BNode, Namespace, RDF, RDFS, Literal, URIRef, XSD, OWL
from rdflib.collection import Collection
import numpy as np

MB_ARTIST_URI_BASE = "https://musicbrainz.org/artist/"

class MSDRDFExtractor:
    def __init__(self):
        self.datadir = "/Users/alo/Data/MillionSongSubset/data"

    def processFile(self, path, includeAnalysis=True):
        file_path = join(self.datadir, path[2], path[3], path[4], path)
        self.h5 = open_h5_file_read(file_path)
        self.convert(includeAnalysis)
        self.h5.close()

    def convert(self, includeAnalysis):
        self.createGraph()
        self.addTrackMetadata()
        self.addReleaseMetadata()
        self.addArtistMetadata()
        self.addGlobalAnalysisData()
        if includeAnalysis:
            self.addAnalysisData()
            self.addSegmentsData()

    def serialize(self, path, rdf_format='n3'):
        self.graph.serialize(path, format=rdf_format)

    def bindNamespaces(self):
        self.ns = {
            'afv': Namespace("https://w3id.org/afo/vocab/1.1#"),
            'afo': Namespace("https://w3id.org/afo/onto/1.1#"),
            'tl': Namespace("http://purl.org/NET/c4dm/timeline.owl#"),
            'event': Namespace("http://purl.org/NET/c4dm/event.owl#"),
            'mo': Namespace("http://purl.org/ontology/mo/"),
            'msd': Namespace("https://labrosa.ee.columbia.edu/millionsong/pages/field-list#"),
            'geo': Namespace("http://www.w3.org/2003/01/geo/wgs84_pos#"),
            'scot': Namespace("http://rdfs.org/scot/ns#"),
            'foaf': Namespace("http://xmlns.com/foaf/0.1/"),
            'dc': Namespace("http://purl.org/dc/elements/1.1/"),
            'owl': Namespace("http://www.w3.org/2002/07/owl#")
        }
        for key in self.ns:
            self.graph.bind(key, self.ns[key])

    def createGraph(self):
        self.graph = Graph()
        self.bindNamespaces()
        self.addCustomTriples()

    def addCustomTriples(self):
        self.graph.add(( URIRef('track_of'), OWL.inverseOf, self.ns['mo']['track'] ))

    def addArtistMetadata(self):
        self.artist_id = URIRef(MB_ARTIST_URI_BASE + get_artist_mbid(self.h5).decode('UTF-8'))
        self.graph.add(( self.release_id, self.ns['foaf']['maker'], self.artist_id ))
        self.graph.add(( self.artist_id, RDF.type, self.ns['mo']['MusicArtist'] ))
        self.graph.add(( self.artist_id, self.ns['msd']['familiarity'], Literal(get_artist_familiarity(self.h5)) ))
        self.graph.add(( self.artist_id, self.ns['msd']['hotttnesss'], Literal(get_artist_hotttnesss(self.h5)) ))
        oid = BNode(get_artist_id(self.h5))
        self.graph.add(( self.artist_id, self.ns['afo']['identifier'], oid ))
        self.graph.add(( oid, self.ns['afo']['origin'], Literal('The Echo Nest artist ID') ))
        self.graph.add(( oid, self.ns['afo']['value'], Literal(get_artist_id(self.h5)) ))
        if get_artist_playmeid(self.h5) != -1:
            oid = BNode(get_artist_playmeid(self.h5))
            self.graph.add(( self.artist_id, self.ns['afo']['identifier'], oid ))
            self.graph.add(( oid, self.ns['afo']['origin'], URIRef('http://playme.com') ))
            self.graph.add(( oid, self.ns['afo']['value'], Literal(get_artist_playmeid(self.h5)) ))
        if get_artist_7digitalid(self.h5) != -1:
            oid = BNode(get_artist_7digitalid(self.h5))
            self.graph.add(( self.artist_id, self.ns['afo']['identifier'], oid ))
            self.graph.add(( oid, self.ns['afo']['origin'], URIRef('https://7digital.com') ))
            self.graph.add(( oid, self.ns['afo']['value'], Literal(get_artist_7digitalid(self.h5)) ))
        oid = BNode()
        self.graph.add(( self.artist_id, self.ns['mo']['origin'], oid ))
        self.graph.add(( oid, self.ns['geo']['location'], Literal(get_artist_location(self.h5)) ))
        if not np.isnan(get_artist_latitude(self.h5)):
            self.graph.add(( oid, self.ns['geo']['lat'], Literal(get_artist_latitude(self.h5)) ))
            self.graph.add(( oid, self.ns['geo']['long'], Literal(get_artist_longitude(self.h5)) ))
        self.graph.add(( self.artist_id, self.ns['foaf']['name'], Literal(get_artist_name(self.h5)) ))
        similar = get_similar_artists(self.h5)
        for sim in similar:
            oid = BNode()
            iid = BNode()
            self.graph.add(( oid, RDF.type, self.ns['mo']['MusicArtist'] ))
            self.graph.add(( iid, self.ns['afo']['origin'], Literal('The Echo Nest artist ID') ))
            self.graph.add(( iid, self.ns['afo']['value'], Literal(sim) ))
            self.graph.add(( oid, self.ns['afo']['identifier'], iid ))
            self.graph.add(( self.artist_id, self.ns['mo']['similar_to'], oid ))
        tags = get_artist_terms(self.h5)
        freqs = get_artist_terms_freq(self.h5)
        wghts = get_artist_terms_weight(self.h5)
        for i in range(len(tags)):
            oid = BNode()
            self.graph.add(( self.artist_id, self.ns['scot']['has_tag'], oid ))
            self.graph.add(( oid, RDFS.label, Literal(tags[i]) ))
            self.graph.add(( oid, self.ns['scot']['own_afrequency'], Literal(freqs[i]) ))
            self.graph.add(( oid, self.ns['scot']['own_rfrequency'], Literal(wghts[i]) ))

    def addReleaseMetadata(self):
        self.release_id = BNode()
        self.graph.add(( self.release_id, RDF.type, self.ns['mo']['Release'] ))
        self.graph.add(( self.release_id, self.ns['dc']['title'], Literal(get_release(self.h5)) ))
        oid = BNode(get_release_7digitalid(self.h5))
        self.graph.add(( self.release_id, self.ns['afo']['identifier'], oid ))
        self.graph.add(( oid, self.ns['afo']['origin'], URIRef('https://7digital.com') ))
        self.graph.add(( oid, self.ns['afo']['value'], Literal(get_release_7digitalid(self.h5)) ))
        oid = BNode()
        if get_year(self.h5) > 0:
            self.graph.add(( oid, self.ns['tl']['at'], Literal(get_year(self.h5)) ))
            self.graph.add(( self.release_id, self.ns['event']['time'], oid ))
        self.graph.add(( self.track_id, URIRef('track_of'), self.release_id ))

    def addTrackMetadata(self):
        self.signal_id = BNode()
        self.track_id = BNode()
        self.timeline_id = BNode()
        self.interval_id = BNode()
        #track
        self.graph.add(( self.track_id, RDF.type, self.ns['mo']['Track'] ))
        self.graph.add(( self.track_id, self.ns['dc']['title'], Literal(get_title(self.h5)) ))
        self.graph.add(( self.track_id, self.ns['msd']['hotttnesss'], Literal(get_song_hotttnesss(self.h5)) ))
        iid = BNode()
        self.graph.add(( iid, self.ns['afo']['origin'], Literal('The Echo Nest track ID') ))
        self.graph.add(( iid, self.ns['afo']['value'], Literal(get_track_id(self.h5)) ))
        self.graph.add(( self.track_id, self.ns['afo']['identifier'], iid ))
        iid = BNode()
        self.graph.add(( iid, self.ns['afo']['origin'], URIRef('https://7digital.com') ))
        self.graph.add(( iid, self.ns['afo']['value'], Literal(get_track_7digitalid(self.h5)) ))
        self.graph.add(( self.track_id, self.ns['afo']['identifier'], iid ))
        iid = BNode()
        self.graph.add(( iid, self.ns['afo']['origin'], Literal('The Echo Nest song ID') ))
        self.graph.add(( iid, self.ns['afo']['value'], Literal(get_song_id(self.h5)) ))
        self.graph.add(( self.track_id, self.ns['afo']['identifier'], iid ))
        #signal
        self.graph.add(( self.signal_id, RDF.type, self.ns['mo']['DigitalSignal'] ))
        self.graph.add(( self.signal_id, self.ns['mo']['sample_rate'], Literal(get_analysis_sample_rate(self.h5)) ))
        self.graph.add(( self.signal_id, self.ns['mo']['published_as'], self.track_id ))
        self.graph.add(( self.timeline_id, RDF.type, self.ns['tl']['Timeline'] ))
        self.graph.add(( self.interval_id, RDF.type, self.ns['tl']['Interval'] ))
        self.graph.add(( self.interval_id, self.ns['tl']['timeline'], self.timeline_id ))
        self.graph.add(( self.interval_id, self.ns['tl']['duration'], Literal(get_duration(self.h5)) ))
        self.graph.add(( self.signal_id, self.ns['event']['time'], self.interval_id ))

    def addGlobalAnalysisData(self):
        fmap = { 'get_audio_md5': 'MD5Checksum', 'get_danceability': 'Danceability', 'get_energy': 'Energy', 'get_loudness': 'Loudness', 'get_tempo': 'Tempo' }
        for key in fmap:
            oid = BNode()
            self.graph.add(( oid, RDF.type, self.ns['afv'][fmap[key]] ))
            self.graph.add(( oid, self.ns['afo']['value'], Literal(eval(key + "(self.h5)")) ))
            self.graph.add(( oid, self.ns['event']['time'], self.interval_id ))
        fmap = { 'get_key': 'Key', 'get_mode': 'Mode', 'get_time_signature': 'TimeSignature' }
        for key in fmap:
            oid = BNode()
            self.graph.add(( oid, RDF.type, self.ns['afv'][fmap[key]] ))
            self.graph.add(( oid, self.ns['afo']['value'], Literal(eval(key + "(self.h5)")) ))
            self.graph.add(( oid, self.ns['afo']['confidence'], Literal(eval(key + "_confidence(self.h5)")) ))
            self.graph.add(( oid, self.ns['event']['time'], self.interval_id ))
        oid = BNode()
        iid = BNode()
        self.graph.add(( iid, RDF.type, self.ns['tl']['Interval'] ))
        self.graph.add(( iid, self.ns['tl']['timeline'], self.timeline_id ))
        self.graph.add(( oid, self.ns['tl']['start'], Literal(0.0) ))
        self.graph.add(( oid, self.ns['tl']['end'], Literal(get_end_of_fade_in(self.h5)) ))
        self.graph.add(( oid, RDF.type, self.ns['afv']['FadeIn'] ))
        self.graph.add(( oid, self.ns['event']['time'], iid ))
        oid = BNode()
        iid = BNode()
        self.graph.add(( iid, RDF.type, self.ns['tl']['Interval'] ))
        self.graph.add(( iid, self.ns['tl']['timeline'], self.timeline_id ))
        self.graph.add(( oid, self.ns['tl']['start'], Literal(get_start_of_fade_out(self.h5)) ))
        self.graph.add(( oid, self.ns['tl']['end'], Literal(get_duration(self.h5)) ))
        self.graph.add(( oid, RDF.type, self.ns['afv']['FadeOut'] ))
        self.graph.add(( oid, self.ns['event']['time'], iid ))

    def addSegmentsData(self):
        at = get_segments_start(self.h5)
        conf = get_segments_confidence(self.h5)
        chroma = get_segments_pitches(self.h5)
        mfcc = get_segments_timbre(self.h5)
        lmax = get_segments_loudness_max(self.h5)
        lmax_time = get_segments_loudness_max_time(self.h5)
        lstart = get_segments_loudness_start(self.h5)
        for i in range(len(at)):
            oid = BNode()
            iid = BNode()
            self.graph.add(( oid, RDF.type, self.ns['afv']['Segment'] ))
            self.graph.add(( oid, self.ns['event']['time'], iid ))
            self.graph.add(( iid, self.ns['tl']['at'], Literal(at[i]) ))
            self.graph.add(( iid, self.ns['tl']['timeline'], self.timeline_id ))
            self.graph.add(( oid, self.ns['event']['time'], iid ))
            self.graph.add(( oid, self.ns['afo']['confidence'], Literal(conf[i]) ))
            iid = BNode()
            self.graph.add(( iid, RDF.type, self.ns['afv']['Chroma'] ))
            self.graph.add(( oid, self.ns['afo']['feature'], iid ))
            listid = BNode()
            self.graph.add(( iid, self.ns['afo']['values'], listid ))
            Collection( self.graph, listid, [ Literal(val) for val in chroma[i] ] )
            iid = BNode()
            self.graph.add(( iid, RDF.type, self.ns['afv']['MFCC'] ))
            self.graph.add(( oid, self.ns['afo']['feature'], iid ))
            listid = BNode()
            self.graph.add(( iid, self.ns['afo']['values'], listid ))
            Collection( self.graph, listid, [ Literal(val) for val in mfcc[i] ] )
            loudness = BNode()
            self.graph.add(( loudness, RDF.type, self.ns['afv']['Loudness'] ))
            self.graph.add(( oid, self.ns['afo']['feature'], loudness ))
            uid = BNode()
            self.graph.add(( uid, RDF.type, self.ns['afv']['Max'] ))
            self.graph.add(( uid, self.ns['afo']['value'], Literal(lmax[i]) ))
            self.graph.add(( loudness, self.ns['afo']['feature'], uid ))
            tid = BNode()
            self.graph.add(( tid, self.ns['tl']['at'], Literal(lmax_time[i]) ))
            self.graph.add(( uid, self.ns['event']['time'], tid ))
            uid = BNode()
            self.graph.add(( uid, RDF.type, self.ns['afv']['First'] ))
            self.graph.add(( uid, self.ns['afo']['value'], Literal(lstart[i]) ))
            self.graph.add(( loudness, self.ns['afo']['feature'], uid ))

    def addAnalysisData(self):
        units = ["sections", "beats", "bars", "tatums"]
        for unit in units:
            name = unit[0:-1].capitalize()
            at = eval("get_" + unit + "_start(self.h5)")
            conf = eval("get_" + unit + "_confidence(self.h5)")
            for i in range(len(at)):
                oid = BNode()
                iid = BNode()
                self.graph.add(( oid, RDF.type, self.ns['afv'][name] ))
                self.graph.add(( oid, self.ns['event']['time'], iid ))
                self.graph.add(( iid, self.ns['tl']['at'], Literal(at[i]) ))
                self.graph.add(( iid, self.ns['tl']['timeline'], self.timeline_id ))
                self.graph.add(( oid, self.ns['event']['time'], iid ))
                self.graph.add(( oid, self.ns['afo']['confidence'], Literal(conf[i]) ))


processAll = True
me = MSDRDFExtractor()

if processAll:
    from os import walk
    from os.path import isfile

    for root, dirs, files in walk("/Users/alo/Data/MillionSongSubset/data/", topdown=False):
        for name in files:
            path = join(root, name)
            if isfile(path):
                me.processFile(path)
                me.serialize("/Users/alo/data/MillionSongSubset/rdf/" + name.split(".")[0] + ".n3")
                print(path)
else:
    me.processFile("TRAAAAW128F429D538.h5", False)
    me.serialize("TRAAAAW128F429D538.n3")
