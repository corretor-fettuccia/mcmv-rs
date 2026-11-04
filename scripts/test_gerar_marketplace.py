"""Testes locais: python3 -m unittest discover -s scripts -p 'test_gerar_marketplace.py' -v"""
import unittest
import xml.etree.ElementTree as ET
from gerar_marketplace import compile_xml,distinct_images,check_contract

def sample():
    return {
        'schemaVersion':4,'sourceContract':'core-imobiliario-v4',
        'snapshotComplete':True,'total_empreendimentos':1,
        'items':[{ 'id':'LINQ_01','name':'LINQ & Canoas',
          'highlight':'Apartamentos em construção, sacada com churrasqueira.',
          'city':'Canoas','uf':'RS', 'address':'Rua Camboatás, 465, Igara',
          'neighborhood':'Marechal Rondon', 'minimum':250000,
          'pageUrl':'https://mcmv-rs.com.br/imoveis/linq/',
          'image':'https://example.com/fachada.webp',
          'gallery':['https://example.com/fachada.webp','https://example.com/piscina.png'],
          'state':'Em construção','propertyType':'Apartamento','bedrooms':2,'bathrooms':1,
          'googleAvailability':'in_stock'}]}

class Tests(unittest.TestCase):
    def test_xml_multifoto_escape_e_preco(self):
        xml,report=compile_xml(sample())
        root=ET.fromstring(xml)
        self.assertEqual(root.findtext('listing/name'),'LINQ & Canoas')
        self.assertEqual(root.findtext('listing/price'),'250000.00 BRL')
        self.assertEqual(len(root.findall('listing/image')),2)
        self.assertIsNone(root.find('listing/neighborhood')) # diverge do endereço
        self.assertEqual(report['incluidos'],1)

    def test_snapshot_incompleto_falha(self):
        data=sample();data['snapshotComplete']=False
        with self.assertRaises(ValueError): compile_xml(data)

    def test_contagem_inconsistente_falha(self):
        data=sample();data['total_empreendimentos']=5
        with self.assertRaises(ValueError): check_contract(data)

    def test_sem_preco_nao_vai_ao_feed(self):
        data=sample();data['items'][0]['minimum']=None
        xml,report=compile_xml(data)
        self.assertEqual(report['incluidos'], 0)
        self.assertEqual(len(ET.fromstring(xml).findall('listing')),0)

    def test_imagens_invalidas_nao_entram(self):
        data=sample()['items'][0]
        data['gallery'].append('file:///etc/passwd')
        self.assertEqual(len(distinct_images(data)),2)

    def test_preco_nao_inventado(self):
        data=sample();data['items'][0]['minimum']='informe-se'
        xml,report=compile_xml(data)
        self.assertEqual(report['incluidos'], 0)
        self.assertEqual(len(ET.fromstring(xml).findall('listing')),0)

    def test_flag_marketplace_independente_google(self):
        data=sample()
        data['items'][0]['googleAvailability']='out_of_stock'
        xml,relatorio=compile_xml(data)
        self.assertEqual(relatorio['incluidos'],1)
        self.assertEqual(ET.fromstring(xml).findtext('listing/home_listing_id'),'LINQ_01')

    def test_flag_marketplace_desativada(self):
        data=sample()
        data['items'][0]['marketplaceEnabled']=False
        xml,report=compile_xml(data)
        self.assertEqual(report['incluidos'], 0)
        self.assertEqual(len(ET.fromstring(xml).findall('listing')),0)

    def test_url_personalizada_para_outros_portais(self):
        data=sample()
        data['nome']='Portal Exemplo'
        data['url_principal']='https://imobiliaria.example/'
        xml,_=compile_xml(data)
        root=ET.fromstring(xml)
        self.assertEqual(root.find('link').attrib['href'],'https://imobiliaria.example/marketplace-produtos.xml')
        self.assertEqual(root.findtext('title'),'Portal Exemplo — Empreendimentos')

if __name__ == '__main__': unittest.main()
