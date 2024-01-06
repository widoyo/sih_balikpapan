from app import ma


class EntryWs(ma.Schema):
    """Schema definisi Wilayah Sungai"""
    id = ma.Integer()
    nama = ma.String()
    
class NewEntryWs(ma.Schema):
    """Schema definisi Wilayah Sungai Baru"""
    nama = ma.String()