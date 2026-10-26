#ifndef KOREAN_CORE_H
#define KOREAN_CORE_H
#include <stdint.h>
#include <stddef.h>
#include <string.h>

static inline uint32_t u32(const void *p) { uint32_t n; memcpy(&n,p,4); return n; }
static inline uint16_t u16(const void *p) { uint16_t n; memcpy(&n,p,2); return n; }
static inline int span(size_t total, uint32_t offset, uint32_t size) { return offset <= total && size <= total-offset; }
static inline uint32_t crc32_bytes(const unsigned char *p, size_t n);
static inline int path_char_equal(char a, char b) {
    if(a=='\\') a='/'; if(b=='\\') b='/';
    if(a>='A' && a<='Z') a=(char)(a+('a'-'A'));
    if(b>='A' && b<='Z') b=(char)(b+('a'-'A'));
    return a==b;
}
static inline int path_equal(const char *a, const char *b) {
    if(!a || !b) return 0;
    while(*a && *b && path_char_equal(*a,*b)) { a++; b++; }
    return !*a && !*b;
}
static inline int path_prefix_equal(const char *a, const char *b) {
    if(!a || !b) return 0;
    while(*b) { if(!*a || !path_char_equal(*a++,*b++)) return 0; }
    return 1;
}
typedef struct { const char *source, *override; uint32_t size, original_crc, replacement_crc; } KoreanFileOverride;
static const KoreanFileOverride korean_file_overrides[]={
        {"Data_aj/Etc2/CHECKJ.TIM","DATA_AJ\\ETC2\\CHECKJ.TIM",153620,0x7d225e41,0x71733a49},
        {"Data_aj/Etc2/FILEGJ03.TIM","DATA_AJ\\ETC2\\FILEGJ03.TIM",22592,0x53d1a3ac,0x85502988},
        {"Data_aj/Etc2/FILEGJ04.TIM","DATA_AJ\\ETC2\\FILEGJ04.TIM",22592,0x8381172f,0x858ba546},
        {"Data_aj/Etc2/FILEGJ05.TIM","DATA_AJ\\ETC2\\FILEGJ05.TIM",22592,0x4d125c26,0xca29cf48},
        {"Data_aj/Etc2/FILEGJ06.TIM","DATA_AJ\\ETC2\\FILEGJ06.TIM",22592,0xf8cb2190,0xf0ce2a73},
        {"Data/Etc/STR_BG.DAT","DATA\\ETC\\STR_BG.DAT",564000,0x0e51d0a3,0xec999291},
        {"Data_j/Etc2/END0.CPT","DATA_J\\ETC2\\END0.CPT",6407,0x3974e19f,0xfa625796},
        {"Data_j/Etc2/END1.CPT","DATA_J\\ETC2\\END1.CPT",8577,0xbdbac365,0x5f296a13},
        {"Data_j/Etc2/FILEGJ.PIX","DATA_J\\ETC2\\FILEGJ.PIX",3782656,0xb751b0d1,0xb4cf3f9b},
        {"Data_j/Etc2/FONTST0J.TIM","DATA_J\\ETC2\\FONTST0J.TIM",33440,0xc382fc2e,0x8763f374},
        {"Data_j/Etc2/FONTST1J.TIM","DATA_J\\ETC2\\FONTST1J.TIM",33440,0x88d82421,0xa9f15746},
        {"Data_j/Etc2/FONTST2J.TIM","DATA_J\\ETC2\\FONTST2J.TIM",33440,0xc5e499e8,0x4ed00d8d},
        {"Data_j/Etc2/FONTST3J.TIM","DATA_J\\ETC2\\FONTST3J.TIM",33440,0xc972d66a,0x4848f8e2},
        {"Data_j/Etc2/FONTST4J.TIM","DATA_J\\ETC2\\FONTST4J.TIM",33440,0x6a112b7c,0x56db5676},
        {"Data_j/Etc2/FONTST5J.TIM","DATA_J\\ETC2\\FONTST5J.TIM",33440,0x2ad4af8b,0xb9baadef},
        {"Data_j/Etc2/FONTST6J.TIM","DATA_J\\ETC2\\FONTST6J.TIM",33440,0x93865ae6,0xe151c5b7},
        {"Data_j/Etc2/FONTST7J.TIM","DATA_J\\ETC2\\FONTST7J.TIM",33440,0xe56845a0,0xcfb781cc},
        {"Data_j/Etc2/INS06.CPT","DATA_J\\ETC2\\INS06.CPT",1945,0x60c8760d,0x2d48c5bf},
        {"Data_j/Etc2/OMBG_J.DAT","DATA_J\\ETC2\\OMBG_J.DAT",1556480,0x6b2afb4b,0x72bb8f2e},
        {"Data_j/Etc2/OPTIONJ.DAT","DATA_J\\ETC2\\OPTIONJ.DAT",534528,0x85e7520d,0x66f90618},
        {"Data_j/Etc2/STMOJIJ.TIM","DATA_J\\ETC2\\STMOJIJ.TIM",9536,0x568df33b,0xdad42306},
        {"Data_j/Etc2/TEXJ.TIM","DATA_J\\ETC2\\TEXJ.TIM",133024,0x9711469d,0xeab4ad57},
        {"Data_j/Etc2/WARNJ.TIM","DATA_J\\ETC2\\WARNJ.TIM",153620,0x4a426dde,0xb1c08620}
    };
static inline const KoreanFileOverride *korean_file_override(const char *path) {
    if(!path) return NULL;
    for(const char *p=path;*p;p++) {
        if((p==path || p[-1]=='/' || p[-1]=='\\' || p[-1]==':') &&
           path_prefix_equal(p,"Bio19/")) {
            const char *relative=p+6;
            for(size_t i=0;i<sizeof korean_file_overrides/sizeof korean_file_overrides[0];i++)
                if(path_equal(relative,korean_file_overrides[i].source)) return &korean_file_overrides[i];
            return NULL;
        }
    }
    return NULL;
}
static inline int korean_file_source_matches(const KoreanFileOverride *file,const unsigned char *data,size_t size) {
    return file && data && size==file->size && crc32_bytes(data,size)==file->original_crc;
}
static inline int korean_file_replacement_matches(const KoreanFileOverride *file,const unsigned char *data,size_t size) {
    return file && data && size==file->size && crc32_bytes(data,size)==file->replacement_crc;
}
static inline int signature_matches(const unsigned char *actual, const unsigned char *expected, size_t n) { return actual && expected && !memcmp(actual,expected,n); }
static inline int font_rect_matches(int x, int y, int w, int h) { return x==768 && y==256 && w==256 && h==256; }
static inline int korean_status_packet_index(const unsigned char *packet,size_t size) {
    static const unsigned char rects[9][4]={
        {0,40,32,16},{72,40,32,16},{32,40,40,16},
        {0,32,24,8},{24,32,40,8},{64,32,40,8},{104,32,40,8},{144,32,32,8},{184,32,32,8}
    };
    if(!packet || size<20 || (packet[7]&0xfc)!=0x64) return -1;
    for(int i=0;i<9;i++)
        if(packet[0x0c]==rects[i][0] && packet[0x0d]==rects[i][1] &&
           u16(packet+0x10)==rects[i][2] && u16(packet+0x12)==rects[i][3]) return i;
    return -1;
}
static inline int korean_font_sprite_packet(const unsigned char *packet,size_t size) {
    return packet && size>=20 && (packet[7]&0xfc)==0x64 &&
        u16(packet+0x10)==14 && u16(packet+0x12)==14 &&
        ((u16(packet+0x0e)>>6)&0x1ff)>=480 && ((u16(packet+0x0e)>>6)&0x1ff)<=511;
}
static inline int diagnostic_seen(uint16_t seen[][9],unsigned count,unsigned limit,const uint16_t fields[9]) {
    if(!seen || !fields || count>=limit) return -1;
    for(unsigned i=0;i<count;i++) if(!memcmp(seen[i],fields,9*sizeof(uint16_t))) return 0;
    memcpy(seen[count],fields,9*sizeof(uint16_t)); return 1;
}
static inline int patch_font_atlas(unsigned char *dst, size_t capacity, const unsigned char *src, size_t source_size, const unsigned char *runs, size_t run_bytes, unsigned count, const unsigned char *files, size_t files_size) {
    const size_t stride=256*2, bytes=stride*256;
    if(!dst || !src || !runs || !files || capacity<bytes || source_size<bytes || count>run_bytes/12) return 0;
    for(unsigned i=0;i<count;i++) {
        const unsigned char *r=runs+i*12;
        unsigned x=u16(r),y=u16(r+2),w=u16(r+4),off=u32(r+8);
        if(x<768 || x+w>896 || !w || y<256 || y>=512 || !span(files_size,off,w*2)) return 0;
    }
    memcpy(dst,src,bytes);
    for(unsigned i=0;i<count;i++) {
        const unsigned char *r=runs+i*12;
        unsigned x=u16(r)-768,y=u16(r+2)-256,w=u16(r+4);
        memcpy(dst+y*stride+x*2,files+u32(r+8),w*2);
    }
    return 1;
}
static inline int image_span(uintptr_t base, uint32_t size, uintptr_t address, size_t length) {
    return address>=base && address-base<=size && length<=size-(address-base);
}
static inline int font_source_span(uintptr_t base, uint32_t size, uintptr_t source, size_t bytes) {
    const size_t expected=256u*256u*2u;
    return bytes==expected && image_span(base,size,source,expected);
}
enum { KOREAN_PATCH_FAILED=0, KOREAN_PATCH_APPLIED=1, KOREAN_PATCH_APPLIED_RESTORE_FAILED=2 };
static inline int korean_patch_succeeded(int result) {
    return result==KOREAN_PATCH_APPLIED || result==KOREAN_PATCH_APPLIED_RESTORE_FAILED;
}
static inline int readable_protection(uint32_t protection) {
    if(protection&0x100) return 0; /* PAGE_GUARD */
    switch(protection&0xff) {
        case 0x02: case 0x04: case 0x08: case 0x20: case 0x40: case 0x80: return 1;
        default: return 0;
    }
}
static inline void rel32_branch(unsigned char out[5], unsigned char opcode, uint32_t site, uint32_t target) {
    out[0]=opcode;
    uint32_t rel=target-(site+5);
    memcpy(out+1,&rel,4);
}
static inline int rel32_target(const unsigned char *branch, uintptr_t site, uintptr_t *target) {
    if(!branch || !target || (branch[0]!=0xe8 && branch[0]!=0xe9)) return 0;
    *target=site+5+(intptr_t)(int32_t)u32(branch+1);
    return 1;
}
enum { KOREAN_FILE_ROUTE_NONE=0, KOREAN_FILE_ROUTE_DIRECT=1, KOREAN_FILE_ROUTE_DDRAW=2 };
static inline int korean_file_loader_route(const unsigned char *entry,uintptr_t site,uintptr_t exe_base,uint32_t exe_size,
                                    const unsigned char *direct_signature,size_t direct_size,
                                    uintptr_t ddraw_base,uint32_t ddraw_size,uint32_t ddraw_rva,
                                    const unsigned char *ddraw_target_bytes,const unsigned char *ddraw_signature,size_t ddraw_signature_size,
                                    uintptr_t *original) {
    if(!entry || !original || !image_span(exe_base,exe_size,site,5)) return KOREAN_FILE_ROUTE_NONE;
    if(image_span(exe_base,exe_size,site,direct_size) && signature_matches(entry,direct_signature,direct_size)) {
        *original=site;
        return KOREAN_FILE_ROUTE_DIRECT;
    }
    uintptr_t target;
    if(entry[0]!=0xe9 || !rel32_target(entry,site,&target) ||
       target!=(uintptr_t)ddraw_base+ddraw_rva ||
       !image_span(ddraw_base,ddraw_size,target,ddraw_signature_size) ||
       !signature_matches(ddraw_target_bytes,ddraw_signature,ddraw_signature_size)) return KOREAN_FILE_ROUTE_NONE;
    *original=target;
    return KOREAN_FILE_ROUTE_DDRAW;
}
static inline uint32_t crc32_bytes(const unsigned char *p, size_t n) {
    uint32_t c=~0u;
    while(n--) { c ^= *p++; for(int k=0;k<8;k++) c=(c>>1)^(0xedb88320u & (0u-(c&1))); }
    return ~c;
}
static const uint32_t korean_hd_diagnostic_keys[]={
    0xcc541949,0x8320a534,0xff1d1b0a,0xca962e6f,0x8d8340ea,
    0xa90ca3ba,0xbebebc1b,0xdacf3586,0x60a06001,0x1ae56ae1
};
enum { KOREAN_HD_DIAG_RESERVED=10, KOREAN_HD_DIAG_CAPACITY=74 };
static inline int korean_hd_diag_record(uint32_t *keys,unsigned char *states,uint32_t key,int success,unsigned *slot) {
    if(!keys || !states || !slot) return 0;
    unsigned at=KOREAN_HD_DIAG_CAPACITY;
    for(unsigned i=0;i<KOREAN_HD_DIAG_RESERVED;i++) if(korean_hd_diagnostic_keys[i]==key) { at=i; break; }
    if(at==KOREAN_HD_DIAG_CAPACITY) {
        for(unsigned i=KOREAN_HD_DIAG_RESERVED;i<KOREAN_HD_DIAG_CAPACITY;i++)
            if(states[i] && keys[i]==key) { at=i; break; }
        if(at==KOREAN_HD_DIAG_CAPACITY)
            for(unsigned i=KOREAN_HD_DIAG_RESERVED;i<KOREAN_HD_DIAG_CAPACITY;i++) if(!states[i]) { at=i; keys[i]=key; break; }
    }
    if(at==KOREAN_HD_DIAG_CAPACITY) return 0;
    *slot=at;
    if(success) { if(states[at]&2) return 0; states[at]|=2; return 1; }
    if(states[at]&1) return 0;
    states[at]|=1;
    if(at<KOREAN_HD_DIAG_RESERVED) keys[at]=key;
    return 1;
}
static inline int korean_hd_lookup_path(uint32_t key,const unsigned char *map,size_t map_size,
                                 const unsigned char *records,size_t records_size,char *path,size_t path_size) {
    if(!map || !records || !path || !path_size || map_size%8 || map_size>1024*1024) return 0;
    size_t lo=0,hi=map_size/8;
    while(lo<hi) { size_t mid=lo+(hi-lo)/2; uint32_t found=u32(map+mid*8); if(found<key) lo=mid+1; else hi=mid; }
    if(lo>=map_size/8 || u32(map+lo*8)!=key) return 0;
    unsigned index=u16(map+lo*8+4);
    if(index>records_size/24 || 24>records_size-(size_t)index*24) return 0;
    const unsigned char *record=records+(size_t)index*24;
    size_t n=0; while(n<16 && record[n]) n++;
    if(!n || n==16) return 0;
    static const char hex[]="0123456789ABCDEF";
    const size_t needed=6+n+1+8+5+1;
    if(needed>path_size) return 0;
    size_t at=0; memcpy(path+at,"hires\\",6); at+=6; memcpy(path+at,record,n); at+=n;
    path[at++]='\\';
    for(int shift=28;shift>=0;shift-=4) path[at++]=hex[(key>>shift)&15];
    memcpy(path+at,".webp",6);
    return 1;
}
static inline int validate_rooms(const unsigned char *b, size_t n) {
    if(n<8 || memcmp(b,"KRM3",4)) return 0;
    uint32_t count=u32(b+4);
    if(count>4096 || count>(n-8)/32) return 0;
    for(uint32_t i=0;i<count;i++) {
        const unsigned char *e=b+8+i*32;
        if(!span(n,u32(e+16),u32(e+20)) || u32(e+28)) return 0;
    }
    return 1;
}
/* Source CRC match, preferring the reported stage. The stage word can lag behind the
   room (R218/R21A load while it still says stage 1), so any stage is tried next. */
static inline const unsigned char *match_room(const unsigned char *blob, const unsigned char *src, size_t available, unsigned stage, uint32_t *index) {
    uint32_t count=u32(blob+4);
    for(int any=0;any<2;any++) {
        for(uint32_t i=0;i<count;i++) {
            const unsigned char *e=blob+8+i*32;
            uint32_t size=u32(e+8);
            if((any || u32(e)==stage) && size<=available && crc32_bytes(src,size)==u32(e+4)) {
                *index=i; return blob+u32(e+16);
            }
        }
    }
    return NULL;
}
#endif
