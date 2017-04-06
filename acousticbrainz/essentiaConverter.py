#!/usr/bin/env python
# -*- coding: utf-8 -*-
import json, numbers, uuid, urllib, httplib2
from rdflib import *
from rdflib.collection import Collection
from rdflib.serializer import Serializer
from pyld import jsonld
import sys

ONTOLOGY = "af-essentia.owl"
URI = "http://sovarr.c4dm.eecs.qmul.ac.uk/af/essentia/"
ACOUSTICBRAINZ_URI = "http://acousticbrainz.org/%s/%s-level"

NAMES_QUERY = """
SELECT ?name WHERE { ?id rdfs:subClassOf* essentia:MirDescriptor ; rdfs:label ?name . }
"""

def dlfake(input):
	'''This is to avoid a bug in PyLD (should be easy to fix and avoid this hack really..)'''
	return {'contextUrl': None,'documentUrl': None,'document': input}

class EssentiaConverter:
    def __init__(self):
        self.ontology = Graph()
        self.ns = Namespace(URI)
        self.ontology.parse(ONTOLOGY, format="n3")
        self.loadNamespaces()

    def reset(self):
        self.loadMap()
        self.identifiers = {}

    def makeFeatureDict(self):
        self.feature_dict = {}
        for it in self.ontology.query(NAMES_QUERY):
            self.feature_dict[str(it.name)] = ""
        self.file_keys = {}
        for key in self.json:
            self.file_keys[key] = self.json[key].keys()

    def loadFile(self, path):
        with open(path) as data_file:
            self.json = json.load(data_file)

    def loadMap(self):
        with open(MAP) as data_file:
            self.map = json.load(data_file)

    def loadNamespaces(self):
        self.namespaces = {}
        self.namespaces["essentia"] = self.ns
        self.namespaces["afo"] = Namespace("https://w3id.org/afo/onto/1.1#")
        self.namespaces["event"] = Namespace("http://purl.org/NET/c4dm/event.owl#")
        self.namespaces["tl"] = Namespace("http://purl.org/NET/c4dm/timeline.owl#")
        self.namespaces["mo"] = Namespace("http://purl.org/ontology/mo/")
        self.namespaces["foaf"] = Namespace("http://xmlns.com/foaf/0.1/")
        self.namespaces["dc"] = Namespace("http://purl.org/dc/elements/1.1/")
        self.namespaces["rdfs"] = RDFS

    def createGraph(self):
        self.graph = Graph()
        self.graph.bind("essentia", self.ns)
        self.graph.bind("afo", self.namespaces["afo"])
        self.graph.bind("event", self.namespaces["event"])
        self.graph.bind("tl", self.namespaces["tl"])
        self.graph.bind("mo", self.namespaces["mo"])
        self.graph.bind("foaf", self.namespaces["foaf"])
        self.graph.bind("dc", self.namespaces["dc"])

    def get(self, musicbrainz_id, feature_type='low', output_format='n3'):
        self.reset()
        uri = ACOUSTICBRAINZ_URI % (musicbrainz_id, feature_type)
        re, co = httplib2.Http().request(uri)
        if re.status == 200:
            self.json = json.loads(co.decode('utf-8'))
            if feature_type == "low":
                self.mapLowLevel()
            else:
                self.mapHighLevel()
            if output_format == 'json-ld':
                context = {}
                for pfx in self.namespaces:
                    context[pfx] = str(self.namespaces[pfx])
                json_rdf = self.graph.serialize(format="json-ld", context=context)
                framed = jsonld.frame(json_rdf, context, options={"documentLoader":dlfake})
                compacted = jsonld.compact(framed, context, options={"documentLoader":dlfake})
                return json.dumps(compacted, indent=2)
            else:
                return self.graph.serialize(format=output_format)
        else:
            return json.dumps(re)

    def loadFrame(self):
        return {
            "@context": {
                "essentia": "http://sovarr.c4dm.eecs.qmul.ac.uk/af/essentia/",
                "foaf": "http://xmlns.com/foaf/0.1/",
                "afo": "https://w3id.org/afo/onto/1.1#",
                "mo": "http://purl.org/ontology/mo/",
                "tl": "http://purl.org/NET/c4dm/timeline.owl#"
            },
            "@type": "mo:Release",
            "foaf:maker": { "@type": "mo:MusicArtist" },
            "mo:publisher": { "@type": "mo:Label" },
            "mo:track": { "@type": "mo:Track", "mo:genre": { "@type": "mo:Genre" } },
            "mo:available_as": {
                "@type": "mo:AudioFile",
                "mo:encodes": {
                    "@type": "essentia:Signal",
                    "mo:time": {
                        "@type": "tl:Timeline",
                        "tl:event": {
                            "@type": "afo:AudioFeature",
                            "afo:feature": {
                                "@type": "afo:AudioFeature",
                                "afo:feature": {
                                    "@type": "afo:AudioFeature"
                                }
                            }
                        }
                    }
                }
            }
        }

    def convertFile(self, source, destination, output_format='n3'):
        self.reset()
        self.loadFile(source)
        if "lowlevel" in self.json:
            self.mapLowLevel()
        else:
            self.mapHighLevel()
        if output_format == 'json-ld':
            context = {}
            for pfx in self.namespaces:
                context[pfx] = str(self.namespaces[pfx])
            json_rdf = self.graph.serialize(format="json-ld", context=context)
            framed = jsonld.frame(json_rdf, self.loadFrame(), options={"documentLoader":dlfake})
            compacted = jsonld.compact(framed, context, options={"documentLoader":dlfake})
            with open(destination, "wb") as write_file:
                write_file.write(json.dumps(compacted, indent=2))
                write_file.close()
        else:
            self.graph.serialize(destination, format=output_format)

    def mapLowLevel(self):
        self.createGraph()
        self.unpackMetadata()
        self.writeVersionInfo()
        for category in self.map:
            for ab_key in self.json[category]:
                struct = self.json[category][ab_key]
                if isinstance(struct, dict):
                    self.unpackDict(category, ab_key)
                else:
                    self.unpackValue(category, ab_key)

    def mapHighLevel(self):
        self.createGraph()
        self.unpackMetadata()
        self.writeVersionInfo()
        self.loadHighLevelKeys()
        hljs = self.json["highlevel"]
        afo = self.namespaces["afo"]
        for feature in self.hl_keys:
            feature_id = BNode()
            type_id = self.namespaces["essentia"]["".join([x.capitalize() for x in feature.split("_")])]
            self.graph.add(( feature_id, RDF.type, type_id ))
            self.graph.add(( feature_id, afo["probability"], Literal(hljs[feature]["probability"]) ))
            self.graph.add(( feature_id, afo["value"], Literal(hljs[feature]["value"]) ))
            self.graph.add(( feature_id, self.namespaces["event"]["time"], self.identifiers["tl:Interval"] ))
            self.graph.add(( feature_id, afo["computed_by"], self.highlevel_extractor ))
            for type_name in hljs[feature]["all"]:
                weight = BNode()
                self.graph.add(( weight, RDFS.label, Literal(type_name) ))
                self.graph.add(( weight, afo["value"], Literal(str(hljs[feature]["all"][type_name])) ))
                self.graph.add(( feature_id, afo["weight"], weight ))

    def writeVersionInfo(self):
        if "highlevel" in self.json["metadata"]["version"]:
            self.highlevel_extractor = BNode("HighLevelExtractor")
            self.graph.add(( self.highlevel_extractor, RDF.type, self.namespaces["essentia"]["HighLevelExtractor"] ))
            version = BNode()
            self.graph.add(( self.highlevel_extractor, self.namespaces["essentia"]["version"], version ))
            for key in self.json["metadata"]["version"]["highlevel"]:
                self.graph.add(( version, self.namespaces["essentia"][key], Literal(self.json["metadata"]["version"]["highlevel"][key]) ))
            lowlevel_version = self.json["metadata"]["version"]["lowlevel"]
        else:
            lowlevel_version = self.json["metadata"]["version"]

        self.lowlevel_extractor = BNode("LowLevelExtractor")
        self.graph.add(( self.lowlevel_extractor, RDF.type, self.namespaces["essentia"]["LowLevelExtractor"] ))
        version = BNode()
        self.graph.add(( self.lowlevel_extractor, self.namespaces["essentia"]["version"], version ))
        for key in lowlevel_version:
            self.graph.add(( version, self.namespaces["essentia"][key], Literal(lowlevel_version[key]) ))

    def createBNode(self):
        return BNode(uuid.uuid4())

    def unpackValue(self, category, key):
        omap = self.map[category][key]
        if omap["class"]:
            oid = self.createBNode()
            self.graph.add(( oid, RDF.type, self.ns[omap["class"]] ))
            self.graph.add(( oid, self.namespaces["event"]["time"], self.identifiers["tl:Interval"] ))
            self.graph.add(( self.identifiers["tl:Interval"], self.namespaces["tl"]["event"], oid ))
            if "feature" in omap:
                sid = self.createBNode()
                self.graph.add(( sid, RDF.type, self.ns[omap["feature"]] ))
                self.graph.add(( oid, self.namespaces["afo"]["feature"], sid ))
                oid = sid
            if type(self.json[category][key]) is list:
                listid = self.createBNode()
                self.graph.add((oid, self.namespaces["afo"]['value'], listid))
                if type(self.json[category][key][0]) is list:
                    idcoll = []
                    for coll in self.json[category][key]:
                        innerid = self.createBNode()
                        idcoll.append(innerid)
                        Collection(self.graph, innerid, [ Literal(val) for val in coll ])
                    Collection(self.graph, listid, idcoll)
                else:
                    Collection(self.graph, listid, [ Literal(val) for val in self.json[category][key] ] )
            else:
                self.graph.add((oid, self.namespaces["afo"]["value"], Literal(self.json[category][key])))

    def unpackDict(self, category, key):
        omap = self.map[category][key]
        oid = self.createBNode()
        self.graph.add(( oid, RDF.type, self.ns[omap["class"]] ))
        self.graph.add(( oid, self.namespaces["afo"]["computed_by"], self.lowlevel_extractor ))
        self.graph.add(( oid, self.namespaces["event"]["time"], self.identifiers["tl:Interval"] ))
        self.graph.add(( self.identifiers["tl:Interval"], self.namespaces["tl"]["event"], oid ))
        if "feature" in omap:
            sid = self.createBNode()
            self.graph.add(( sid, RDF.type, self.ns[omap["feature"]] ))
            self.graph.add(( oid, self.namespaces["afo"]["feature"], sid ))
            oid = sid

        for stat in self.json[category][key].keys():
            sub = [ it for it in self.ontology.query("SELECT ?sub WHERE { ?sub essentia:annotation_key '%s' }" % stat) ][0][0]
            sid = self.createBNode()
            self.graph.add(( sid, RDF.type, sub ))
            self.graph.add(( oid, self.namespaces["afo"]["feature"], sid ))
            if type(self.json[category][key][stat]) is list:
                listid = self.createBNode()
                self.graph.add((sid, self.namespaces["afo"]['values'], listid))
                if type(self.json[category][key][stat][0]) is list:
                    dimid = self.createBNode()
                    dimensions = [ Literal(len(self.json[category][key][stat])), Literal(len(self.json[category][key][stat][0])) ]
                    flattened = [ Literal(val) for arr in self.json[category][key][stat] for val in arr ]
                    Collection(self.graph, listid, flattened)
                    self.graph.add((sid, self.namespaces["afo"]["dimensions"], dimid))
                    Collection(self.graph, dimid, dimensions)
                else:
                    Collection(self.graph, listid, [ Literal(val) for val in self.json[category][key][stat] ] )
            else:
                self.graph.add((sid, self.namespaces["afo"]["value"], Literal(self.json[category][key][stat])))

    def unpackMetadata(self):
        for obj_key in self.map["metadata"]["bnodes"]:
            ns, obj = obj_key.split(":")
            self.identifiers[obj_key] = self.createBNode()
            self.graph.add(( self.identifiers[obj_key], RDF.type, self.namespaces[ns][obj] ))
        for struct in self.map["metadata"]["identities"]:
            ns, obj = struct["class"].split(':')
            if struct["source"] in self.json["metadata"]["tags"]:
                value = self.getTagValue(self.json["metadata"]["tags"][struct["source"]])
                self.identifiers[struct["class"]] = URIRef((struct["root"] + self.quote(value)))
            else:
                self.identifiers[struct["class"]] = self.createBNode()
            self.graph.add(( self.identifiers[struct["class"]], RDF.type, self.namespaces[ns][obj] ))
        for struct in self.map["metadata"]["links"]:
            prd_ns, prd_obj = struct["property"].split(':')
            self.graph.add(( self.identifiers[struct["source"]], self.namespaces[prd_ns][prd_obj], self.identifiers[struct["target"]] ))

        del self.map["metadata"]["bnodes"]
        del self.map["metadata"]["identities"]
        del self.map["metadata"]["links"]

        for category in self.map["metadata"]:
            for json_key in self.map["metadata"][category]:
                if json_key in self.json["metadata"][category]:
                    struct = self.map["metadata"][category][json_key]
                    prd_ns, prd_val = struct["property"].split(':')
                    if "type" in struct:
                        typ_ns, typ_val = struct["type"].split(':')
                        value = Literal(self.getTagValue(self.json["metadata"][category][json_key]), datatype=XSD[typ_val])
                    elif "individuals" in struct:
                        tag_value = self.getTagValue(self.json["metadata"][category][json_key])
                        if tag_value.lower() in struct["individuals"]:
                            obj_ns, obj_val = struct["individuals"][tag_value.lower()].split(':')
                            value = self.namespaces[obj_ns][obj_val]
                        else:
                            value = Literal(self.getTagValue(self.json["metadata"][category][json_key]))
                    else:
                        value = Literal(self.getTagValue(self.json["metadata"][category][json_key]))
                    self.graph.add(( self.identifiers[struct["class"]], self.namespaces[prd_ns][prd_val], value ))

        del self.map["metadata"]

    def refactorLists(self, json_rdf):
        json_rdf = json.loads(json_rdf)
        for item in json_rdf["@graph"]:
            if "@type" in item and (item["@type"] == "essentia:InverseCovariance" or item["@type"] == "essentia:Covariance"):
                dimensions = { "@list": [ len(item["afo:values"]["@list"]), len(item["afo:values"]["@list"][0]["@list"]) ] }
                flattened = [ outerlist["@list"] for outerlist in item["afo:values"]["@list"] ]
                item["afo:dimensions"] = dimensions
                item["afo:values"] = { "@list": flattened }
        return json.dumps(json_rdf)

    def quote(self, value):
        try:
            value = value.replace(" ", "+")
            URIRef(value).n3()
        except Exception as ex:
            value = urllib.quote(unicode(value))
        else:
            pass
        return value

    def getTagValue(self, value):
        if type(value) is list:
            return value[0]
        else:
            return value

    def serialize(self, path):
        self.graph.serialize(path, format='n3')

    def loadMap(self):
        #with open(MAP) as data_file:
        #    self.map = json.load(data_file)
        self.map = {
          "lowlevel": {
            "average_loudness": { "class": "Loudness", "feature": "Mean" },
            "barkbands": { "class": "BarkBands" },
            "barkbands_crest": { "class": "BarkBands", "feature": "Crest" },
            "barkbands_flatness_db": { "class": "BarkBands", "feature": "FlatnessDB" },
            "barkbands_kurtosis": { "class": "BarkBands", "feature": "Kurtosis" },
            "barkbands_skewness": { "class": "BarkBands", "feature": "Skewness" },
            "barkbands_spread": { "class": "BarkBands", "feature": "Spread" },
            "dissonance": { "class": "Dissonance" },
            "dynamic_complexity": { "class": "DynamicComplexity" },
            "erbbands": { "class": "ERBBands" },
            "erbbands_crest": { "class": "ERBBands", "feature": "Crest" },
            "erbbands_flatness_db": { "class": "ERBBands", "feature": "FlatnessDB" },
            "erbbands_kurtosis": { "class": "ERBBands", "feature": "Kurtosis" },
            "erbbands_skewness": { "class": "ERBBands", "feature": "Skewness" },
            "erbbands_spread": { "class": "ERBBands", "feature": "Spread" },
            "gfcc": { "class": "GFCC" },
            "hfc": { "class": "HFC" },
            "melbands": { "class": "MelBands"},
            "melbands_crest": { "class": "MelBands", "feature": "Crest" },
            "melbands_flatness_db": { "class": "MelBands", "feature": "FlatnessDB" },
            "melbands_kurtosis": { "class": "MelBands", "feature": "Kurtosis" },
            "melbands_skewness": { "class": "MelBands", "feature": "Skewness" },
            "melbands_spread": { "class": "MelBands", "feature": "Spread" },
            "mfcc": { "class": "MFCC" },
            "pitch_salience": { "class": "PitchSalience"},
            "silence_rate_20dB": { "class": "SilenceRate", "parameter": { "name": "thresholds", "value": [ 20 ], "unit": "db" } },
            "silence_rate_30dB": { "class": "SilenceRate", "parameter": { "name": "thresholds", "value": [ 30 ], "unit": "db" } },
            "silence_rate_60dB": { "class": "SilenceRate", "parameter": { "name": "thresholds", "value": [ 60 ], "unit": "db" } },
            "spectral_centroid": { "class": "Centroid" },
            "spectral_complexity": { "class": "SpectralComplexity" },
            "spectral_contrast_coeffs": { "class": "SpectralContrast" },
            "spectral_contrast_valleys": { "class": "SpectralValley" },
            "spectral_decrease": { "class": "Decrease" },
            "spectral_energy": { "class": "Energy" },
            "spectral_energyband_high": { "class": "EnergyBand", "parameter": [ { "name": "startCutoffFrequency", "value": 4000, "unit": "Hz" }, { "name": "stopCutoffFrequency", "value": 20000, "unit": "Hz" } ] },
            "spectral_energyband_low": { "class": "EnergyBand", "parameter": [ { "name": "startCutoffFrequency", "value": 20, "unit": "Hz" }, { "name": "stopCutoffFrequency", "value": 150, "unit": "Hz" } ] },
            "spectral_energyband_middle_high": { "class": "EnergyBand", "parameter": [ { "name": "startCutoffFrequency", "value": 800, "unit": "Hz" }, { "name": "stopCutoffFrequency", "value": 4000, "unit": "Hz" } ] },
            "spectral_energyband_middle_low": { "class": "EnergyBand", "parameter": [ { "name": "startCutoffFrequency", "value": 150, "unit": "Hz" }, { "name": "stopCutoffFrequency", "value": 800, "unit": "Hz" } ] },
            "spectral_entropy": { "class": "Entropy" },
            "spectral_flux": { "class": "Flux" },
            "spectral_kurtosis": { "class": "Kurtosis" },
            "spectral_rms": { "class": "RMS" },
            "spectral_rolloff": { "class": "RollOff" },
            "spectral_skewness": { "class": "Skewness" },
            "spectral_spread": { "class": "Spread" },
            "spectral_strongpeak": { "class": "StrongPeak" },
            "zerocrossingrate": { "class": "ZeroCrossingRate" }
          },
          "rhythm": {
            "beats_loudness": { "class": "BeatsLoudness" },
            "beats_loudness_band_ratio": { "class": "BeatsLoudnessBandRatio" },
            "beats_position": { "class": "BeatsPosition" },
            "bpm": { "class": "BPM" },
            "bpm_histogram_first_peak_bpm": { "class": "FirstPeakBPM" },
            "bpm_histogram_first_peak_spread": { "class": "FirstPeakSpread" },
            "bpm_histogram_first_peak_weight": { "class": "FirstPeakWeight" },
            "bpm_histogram_second_peak_bpm": { "class": "SecondPeakBPM" },
            "bpm_histogram_second_peak_spread": { "class": "SecondPeakSpread" },
            "bpm_histogram_second_peak_weight": { "class": "SecondPeakWeight" },
            "danceability": { "class": "Danceability" },
            "onset_rate": { "class": "OnsetRate" },
            "beats_count": { "class": "BeatsCount" }
          },
          "tonal": {
            "thpcp": { "class": "THPCP" },
            "chords_number_rate": { "class": "ChordsNumberRate" },
            "chords_scale": { "class": "ChordsScale" },
            "chords_changes_rate": { "class": "ChordsChangesRate" },
            "key_strength": { "class": "KeyStrength" },
            "tuning_diatonic_strength": { "class": "KeyStrength", "parameter": { "name": "profileType", "value": "diatonic" } },
            "hpcp_entropy": { "class": "HPCP", "feature": "Entropy" },
            "key_scale": { "class": "KeyScale" },
            "chords_strength": { "class": "ChordsStrength" },
            "key_key": { "class": "Key" },
            "tuning_nontempered_energy_ratio": { "class": "NonTemperedEnergyRatio" },
            "tuning_equal_tempered_deviation": { "class": "EqualTemperedDeviation" },
            "chords_histogram": { "class": "ChordsHistogram" },
            "chords_key": { "class": "ChordsKey" },
            "tuning_frequency": { "class": "TuningFrequency" },
            "hpcp": { "class": "HPCP" }
          },
          "metadata": {
            "bnodes": [ "essentia:Signal", "tl:Interval", "tl:Timeline", "mo:Genre", "mo:Label", "essentia:VersionInfo" ],
            "identities": [
              { "class": "mo:MusicArtist", "source": "musicbrainz_artistid", "root": "http://musicbrainz.org/artist/" },
              { "class": "mo:MusicArtist", "source": "musicbrainz_albumartistid", "root": "http://musicbrainz.org/artist/" },
              { "class": "mo:Release", "source": "musicbrainz_albumid", "root": "http://musicbrainz.org/release/"  },
              { "class": "mo:Track", "source": "musicbrainz_recordingid", "root": "http://musicbrainz.org/recording/" },
              { "class": "mo:AudioFile", "source": "file_name", "root": "" }
            ],
            "links": [
              { "source": "mo:Track", "target": "mo:AudioFile", "property": "mo:available_as" },
              { "source": "tl:Interval", "target": "tl:Timeline", "property": "tl:timeline" },
              { "source": "tl:Timeline", "target": "tl:Interval", "property": "tl:interval" },
              { "source": "mo:Release", "target": "mo:Label", "property": "mo:publisher" },
              { "source": "mo:Release", "target": "mo:Track", "property": "mo:track" },
              { "source": "mo:Track", "target": "mo:Genre", "property": "mo:genre" },
              { "source": "mo:AudioFile", "target": "essentia:Signal", "property": "mo:encodes" },
              { "source": "mo:Release", "target": "mo:MusicArtist", "property": "foaf:maker" },
              { "source": "essentia:Signal", "target": "tl:Interval", "property": "mo:time" }
            ],
            "audio_properties": {
              "sample_rate": { "class": "essentia:Signal", "property": "mo:sample_rate", "type": "xsd:interger" },
              "codec": { "class": "essentia:Signal", "property": "essentia:codec", "type": "xsd:string" },
              "downmix": { "class": "essentia:Signal", "property": "essentia:downmix", "type": "xsd:string" },
              "equal_loudness": { "class": "essentia:Signal", "property": "essentia:equal_loudness", "type": "xsd:float" },
              "lossless": { "class": "essentia:Signal", "property": "essentia:lossless", "type": "xsd:boolean" },
              "md5_encoded": { "class": "essentia:Signal", "property": "essentia:md5_encoded", "type": "xsd:string" },
              "replay_gain": { "class": "essentia:Signal", "property": "essentia:replay_gain", "type": "xsd:float" },
              "bit_rate": { "class": "essentia:Signal", "property": "essentia:bit_rate", "type": "xsd:float" },
              "length": { "class": "tl:Interval", "property": "tl:duration", "type": "xsd:duration" }
            },
            "tags": {
              "album": { "class": "mo:Release", "property": "dc:title" },
              "artist": { "class": "mo:MusicArtist", "property": "foaf:name" },
              "albumartist": { "class": "mo:MusicArtist", "property": "foaf:name" },
              "asin": { "class": "mo:Release", "property": "essentia:asin" },
              "barcode": { "class": "mo:Release", "property": "essentia:barcode" },
              "catalognumber": { "class": "mo:Release", "property": "mo:catalogue_number" },
              "date": { "class": "mo:Release", "property": "dc:date" },
              "genre": { "class": "mo:Genre", "property": "rdfs:label" },
              "label": { "class": "mo:Label", "property": "foaf:name" },
              "musicbrainz album release country": { "class": "mo:Release", "property": "mo:publishing_location" },
              "musicbrainz album status": { "class": "mo:Release", "property": "mo:release_status", "individuals": { "official": "mo:official", "promotion": "mo:promotion", "bootleg": "mo:bootleg", "pseudo-release": "mo:pseudo_release" } },
              "musicbrainz album type": { "class": "mo:Release", "property": "mo:release_type", "individuals": {
                "album": "mo:album",
                "compilation": "mo:compilation",
                "album/compilation": "mo:compilation",
                "other/audiobook": "mo:audiobook",
                "soundtrack": "mo:soundtrack",
                "album/soundtrack": "mo:soundtrack",
                "album/live/soundtrack": "mo:album",
                "spokenword": "mo:spokenword",
                "album/compilation/live": "mo:album"
                }
              },
              "musicbrainz trm id": { "class": "mo:Track", "property": "essentia:musicbrainz_trm_id" },
              "musicmagic data": { "class": "mo:Track", "property": "essentia:musicmagic_data" },
              "musicmagic fingerprint": { "class": "mo:Track", "property": "essentia:musicmagic_fingerprint" },
              "replaygain_album_gain": { "class": "mo:Release", "property": "essentia:replay_gain" },
              "replaygain_track_gain": { "class": "mo:Track", "property": "essentia:replay_gain" },
              "replaygain_track_peak": { "class": "mo:Track", "property": "essentia:replay_peak" },
              "title": { "class": "mo:Track", "property": "dc:title" },
              "tracknumber": { "class": "mo:Track", "property": "mo:track_number" }
            }
          }
        }

    def loadHighLevelKeys(self):
        self.hl_keys = [u'timbre', u'ismir04_rhythm', u'voice_instrumental', u'gender', u'genre_rosamerica', u'mood_electronic', u'genre_electronic', u'mood_sad', u'tonal_atonal', u'mood_party', u'moods_mirex', u'danceability', u'genre_dortmund', u'mood_acoustic', u'mood_happy', u'mood_aggressive', u'genre_tzanetakis', u'mood_relaxed']

def main():
	print sys.argv[1]
	if (sys.argv[1] is None or len(sys.argv[1]) != 36):
		print("invalid MusicBrainz recording ID, exiting..")
	else:
		c = EssentiaConverter()
		n3 = c.get(sys.argv[1])
		if not sys.argv[2] is None:
			c.serialize(sys.argv[2])
		else:
			return n3

if __name__ == "__main__":
    main()
