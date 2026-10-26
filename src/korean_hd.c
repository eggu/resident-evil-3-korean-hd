#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <wincrypt.h>
#include <stdio.h>
#include <stdarg.h>
#include "korean_core.h"

#ifndef KOREAN_HD_VERSION
#define KOREAN_HD_VERSION "dev"
#endif

static unsigned char *rooms, *files;
static DWORD rooms_size, files_size;
static unsigned char *font_runs;
static unsigned font_count;
static char folder[MAX_PATH], exe_path[MAX_PATH];
static int active;
/* Classic REbirth ddraw.dll builds this mod knows. Every RVA below was verified against that
   exact file; add a row (and its SHA256) to support another build. */
typedef struct {
    const char *name; uint32_t file_size; unsigned char sha256[32];
    uint32_t upload;                                   /* texture upload wrapper the exe jumps to */
    uint32_t lookup, lookup_end_global, store, messages; /* codepoint lookup, message store and table */
    uint32_t menu_returns[3];                          /* menu glyph renderer callers of lookup */
    uint32_t cell_site, cell_tail, cell_f2;            /* menu glyph cell selection */
    uint32_t menu_base_site, menu_one, menu_list;      /* load-menu text pointers */
    uint32_t own_slot[4], own_japanese[4];             /* load/save/yes/no strings kept in ddraw */
} RebirthProfile;
static const RebirthProfile rebirth_profiles[]={
    {"1.0.3",5666816,{0x8e,0xf0,0x95,0x11,0xa5,0x61,0x25,0x74,0xb2,0x40,0xe6,0x02,0xb1,0x9b,0xd1,0x69,
                      0x2a,0x2c,0x33,0xbd,0x0c,0x1a,0x5f,0xab,0x13,0x48,0x73,0x8c,0x70,0xc6,0x44,0x23},
     0xa8480, 0x74f90,0x701200,0xab490,0x4020b0, {0xb6964,0xb6c28,0xb6c67}, 0xb6a2d,0xb6aba,0xb6a55,
     0xcd18b,0x7ca2a8,0x7ca2b4, {0x7ca298,0x7ca29c,0x7ca2ac,0x7ca2b0}, {0x3f601c,0x3f6028,0x3f6034,0x3f603c}},
};
static const RebirthProfile *rb;
static HMODULE lookup_ddraw_module;
static int module_image_size32(HMODULE module,uint32_t *size);
typedef struct { short x,y,w,h; } Rect;
typedef int (__cdecl *Upload)(const Rect *, const void *);
static Upload original_upload;
static unsigned char atlas[256*256*2];
static int patch(void *dst,const void *src,size_t n);
static int branch(void *site,void *target,unsigned char opcode);
static int branch8(void *site,void *target,unsigned char opcode);
static int branch9(void *site,void *target,unsigned char opcode);
/* KRX1: Steam KRP1 text tables ported to SourceNext by tools/build_exe_text.py. */
static unsigned char *exe_text_alloc;
static uint32_t item_operand_values[2];
static const uintptr_t item_operand_sites[2]={0x431a53,0x431a59};

static void log_line(const char *fmt, ...) {
    char path[MAX_PATH]; snprintf(path,sizeof path,"%skorean_hd.log",folder);
    FILE *f=fopen(path,"a"); if(!f) return;
    va_list args; va_start(args,fmt); vfprintf(f,fmt,args); va_end(args);
    fputc('\n',f); fclose(f);
}
static unsigned char *read_blob(const char *name,DWORD *size) {
    char path[MAX_PATH]; snprintf(path,sizeof path,"%s%s",folder,name);
    HANDLE f=CreateFileA(path,GENERIC_READ,FILE_SHARE_READ,NULL,OPEN_EXISTING,0,NULL);
    if(f==INVALID_HANDLE_VALUE) return NULL;
    *size=GetFileSize(f,NULL);
    if(*size==INVALID_FILE_SIZE || *size>16*1024*1024) { CloseHandle(f); return NULL; }
    unsigned char *b=HeapAlloc(GetProcessHeap(),0,*size); DWORD got=0;
    int ok=b && ReadFile(f,b,*size,&got,NULL) && got==*size;
    CloseHandle(f); if(!ok) { if(b) HeapFree(GetProcessHeap(),0,b); return NULL; }
    return b;
}
static int load_fonts(void) {
    if(files_size<12 || memcmp(files,"KRF2",4)) return 0;
    unsigned count=u32(files+4), run_count=0;
    font_count=u32(files+8);
    if(count>4096 || count>(files_size-12)/40) return 0;
    for(unsigned i=0;i<count;i++) {
        const unsigned char *e=files+12+i*40;
        unsigned start=u32(e+32), len=u32(e+36);
        if(start>1000000 || len>1000000-start) return 0;
        if(start+len>run_count) run_count=start+len;
    }
    unsigned offset=12+count*40+run_count*12;
    if(offset>files_size || font_count>(files_size-offset)/12) return 0;
    font_runs=files+offset;
    for(unsigned i=0;i<font_count;i++) {
        const unsigned char *r=font_runs+i*12;
        unsigned x=u16(r),y=u16(r+2),w=u16(r+4);
        if(x<768 || x+w>896 || !w || y<256 || y>=512 || !span(files_size,u32(r+8),w*2)) return 0;
    }
    return 1;
}
/* KRB2: Hangul -> KRF2 token entries checked before REbirth's codepoint lookup
   (rb->lookup), plus Korean UTF-16 fed to its message store (rb->store);
   see tools/build_rebirth_text.py. */
enum { RB_MESSAGE_LIMIT=0x40 };
typedef uint32_t (__stdcall *RbLookup)(uint32_t);
typedef void (__fastcall *RbStore)(const void *,uint32_t);
static unsigned char *rebirth_blob;
static DWORD rebirth_size;
static RbLookup original_rb_lookup;
/* Only REbirth's menu glyph renderer and its width measures (rb->menu_returns) get Hangul codes;
   other callers index tables with the full code unchecked (crashes on the status screen). */
static uint32_t __stdcall rb_lookup_hook(uint32_t cp) {
    uint32_t caller=(uint32_t)((uintptr_t)__builtin_return_address(0)-(uintptr_t)lookup_ddraw_module), code=0;
    int allowed=0;
    for(unsigned i=0;i<3;i++) if(caller==rb->menu_returns[i]) allowed=1;
    uint32_t lo=0,hi=u32(rebirth_blob+4);
    const unsigned char *g=rebirth_blob+8;
    while(allowed && lo<hi) {
        uint32_t mid=(lo+hi)/2, key=u16(g+mid*4);
        if(key==cp) { code=u16(g+mid*4+2); break; }
        if(key<cp) lo=mid+1; else hi=mid;
    }
    if(!code) code=original_rb_lookup(cp);
    return code;
}
/* REbirth's menu renderer special-cases only EA/EB/F2 and treats EB unlike the game. Mirror
   the game's prefix table (0x431280): page, row offset, CLUT row; u=(b%18)*14, v=(b/18+row)*14. */
uint32_t rb_cell_tail, rb_cell_f2;
uint32_t __cdecl __attribute__((used)) rb_cell(uint32_t code,unsigned char *sprite) {
    static const uint16_t layer[6][3]={{0x1d,0,490},{0x1d,14,490},{0x1c,0,500},{0x1c,14,500},{0x1d,0,500},{0x1d,14,500}};
    unsigned hi=code>>8&0xff,b=code&0xff;
    if(hi==0xf2) return 0xffffffffu;
    if(hi<0xeb || hi>0xf0) return code%18 | ((code/18+2)*14&0xff)<<8;
    const uint16_t *k=layer[hi-0xeb];
    uint16_t clut=u16(sprite+0x12),page=k[0];
    unsigned y=clut>>6,shade=y>=480 ? (y-480)%10 : 0;  /* keep REbirth's colour/shadow row offset */
    clut=(uint16_t)((k[2]+shade)<<6 | (clut&0x3f));
    memcpy(sprite+4,&page,2); memcpy(sprite+0x12,&clut,2);
    return b%18 | ((b/18+k[1])*14&0xff)<<8;
}
__attribute__((naked)) static void rb_cell_stub(void) {
    __asm__ volatile(
        "push %esi\n\tpushl -0x24(%ebp)\n\tcall _rb_cell\n\tadd $8,%esp\n\t"
        "cmp $-1,%eax\n\tje 1f\n\tmov %al,%dl\n\tmov %ah,%cl\n\tjmp *_rb_cell_tail\n"
        "1:\n\tmovzwl -0x24(%ebp),%edx\n\tjmp *_rb_cell_f2\n");
}
static int hook_rb_cell(unsigned char *dd,uint32_t dd_size) {
    static const unsigned char expected[]={0x81,0xf9,0x00,0xeb,0x00,0x00,0x74,0x3b,0x81,0xf9,0x00,0xf2,0x00,0x00,0x74,0x18,0x8b,0x45,0xdc};
    if(!image_span((uintptr_t)dd,dd_size,(uintptr_t)dd+rb->cell_site,sizeof expected) || !signature_matches(dd+rb->cell_site,expected,sizeof expected)) return 0;
    rb_cell_tail=(uint32_t)(uintptr_t)(dd+rb->cell_tail); rb_cell_f2=(uint32_t)(uintptr_t)(dd+rb->cell_f2);
    return branch8(dd+rb->cell_site,rb_cell_stub,0xe9);
}
static int load_rebirth_text(void) {
    if(!lookup_ddraw_module) { log_line("REbirth text skipped: verified DDraw unavailable"); return 0; }
    rebirth_blob=read_blob("korean_rebirth.bin",&rebirth_size);
    if(!rebirth_blob) { log_line("REbirth text skipped: cannot read korean_rebirth.bin"); return 0; }
    unsigned char *dd=(unsigned char *)lookup_ddraw_module;
    uint32_t dd_size=0; module_image_size32(lookup_ddraw_module,&dd_size);
    const unsigned char *s=NULL,*end=rebirth_blob+rebirth_size;
    uint32_t strings=0;
    int ok=rebirth_size>=12 && !memcmp(rebirth_blob,"KRB2",4) && u32(rebirth_blob+4)<4096 && span(rebirth_size,8,u32(rebirth_blob+4)*4+4);
    if(ok) { s=rebirth_blob+8+u32(rebirth_blob+4)*4; strings=u32(s); s+=4; }
    const unsigned char *first=s;
    for(uint32_t i=0;ok && i<strings;i++) {  /* id, imm32 RVA, original text RVA, UTF-16 chars */
        uint32_t chars=end-s>=16 ? u32(s+12) : 0;
        ok=chars && chars<256 && (size_t)(end-s-16)>=chars*2u && u32(s)<RB_MESSAGE_LIMIT &&
           image_span((uintptr_t)dd,dd_size,(uintptr_t)dd+u32(s+4),4) && u32(dd+u32(s+4))==(uint32_t)(uintptr_t)(dd+u32(s+8));
        if(ok) s+=16+chars*2u;
    }
    static const unsigned char prologue[]={0x55,0x8b,0xec,0x8b,0x0d};
    ok=ok && s==end && image_span((uintptr_t)dd,dd_size,(uintptr_t)dd+rb->lookup,9) && signature_matches(dd+rb->lookup,prologue,sizeof prologue) &&
       u32(dd+rb->lookup+5)==(uint32_t)(uintptr_t)(dd+rb->lookup_end_global);
    void *trampoline=ok ? VirtualAlloc(NULL,32,MEM_COMMIT|MEM_RESERVE,PAGE_EXECUTE_READWRITE) : NULL;
    if(!trampoline) {
        log_line("REbirth text skipped: %s",ok?"allocation failed":"blob or DDraw guard failed");
        HeapFree(GetProcessHeap(),0,rebirth_blob); rebirth_blob=NULL; return 0;
    }
    memcpy(trampoline,dd+rb->lookup,9);  /* push ebp; mov ebp,esp; mov ecx,[abs] (already relocated) */
    if(!branch((unsigned char *)trampoline+9,dd+rb->lookup+9,0xe9)) { VirtualFree(trampoline,0,MEM_RELEASE); return 0; }
    original_rb_lookup=(RbLookup)trampoline;
    if(!branch9(dd+rb->lookup,rb_lookup_hook,0xe9)) { VirtualFree(trampoline,0,MEM_RELEASE); original_rb_lookup=NULL; return 0; }
    RbStore store=(RbStore)(dd+rb->store);
    s=first;
    for(uint32_t i=0;i<strings;i++) {
        const unsigned char *text=s+16; uint32_t ptr=(uint32_t)(uintptr_t)text;
        patch(dd+u32(s+4),&ptr,4);  /* later re-initialisation stores Korean too */
        if(u32(dd+rb->messages+u32(s)*4)) store(text,u32(s));  /* only replace a message REbirth already stored */
        s+=16+u32(s+12)*2u;
    }
    log_line("REbirth text applied: %lu Hangul glyphs, %lu messages, menu cell hook=%d",(unsigned long)u32(rebirth_blob+4),(unsigned long)strings,hook_rb_cell(dd,dd_size));
    return 1;
}
/* REbirth's item-table initializer rewrites these operands with its own Japanese table. */
static void reapply_item_operands(void) {
    for(unsigned i=0;i<2;i++) {
        if(!item_operand_values[i] || u32((void *)item_operand_sites[i])==item_operand_values[i]) continue;
        log_line("item operand %08lx reset from %08X",(unsigned long)item_operand_sites[i],u32((void *)item_operand_sites[i]));
        patch((void *)item_operand_sites[i],&item_operand_values[i],4);
    }
}
/* REbirth fills its load-menu text pointers (code at RVA 0xCD17E: one entry from offset word
   0x52BF68, fourteen from 0x52BFD2..0x52BFEE, all + table base 0x52BB04) before post-init, so
   they still point into the Japanese table. Recompute any that do from the Korean base. */
enum { RB_MENU_LIST_COUNT=14, JP_MENU_TABLE=0x52bb04, JP_MENU_TABLE_END=0x52dea0 };
static unsigned rebuild_rb_menu_pointers(unsigned char *dd,uint32_t dd_size) {
    if(!image_span((uintptr_t)dd,dd_size,(uintptr_t)dd+rb->menu_list,RB_MENU_LIST_COUNT*4) || !image_span((uintptr_t)dd,dd_size,(uintptr_t)dd+rb->menu_base_site,4)) return 0;
    uint32_t base=u32(dd+rb->menu_base_site);
    if(base==JP_MENU_TABLE) return 0;  /* Korean base not patched */
    uint32_t *slot[1+RB_MENU_LIST_COUNT]; uint32_t word[1+RB_MENU_LIST_COUNT];
    slot[0]=(uint32_t *)(dd+rb->menu_one); word[0]=0x52bf68;
    for(unsigned i=0;i<RB_MENU_LIST_COUNT;i++) { slot[1+i]=(uint32_t *)(dd+rb->menu_list)+i; word[1+i]=0x52bfd2+2*i; }
    unsigned n=0;
    for(unsigned i=0;i<1+RB_MENU_LIST_COUNT;i++) {
        uint32_t v=*slot[i];
        if(v<JP_MENU_TABLE || v>=JP_MENU_TABLE_END) continue;  /* not built yet, or already Korean */
        *slot[i]=base+u16((void *)(uintptr_t)word[i]); n++;
    }
    /* The same builder points four slots at Japanese strings stored in DDraw itself. */
    static const unsigned char dont_save[]={0xed,0xf9,0xed,0xb4,0xf6,0xed,0x57,0xf6,0xeb,0x94,0xfe},  /* 저장 안 함 */
        dont_load[]={0xee,0x14,0xed,0x59,0xed,0x52,0xed,0x2b,0xf6,0xed,0x5e,0xed,0x6d,0xfe},         /* 불러오지 않음 */
        yes[]={0xeb,0x14,0xfe}, no[]={0xed,0x32,0xed,0xad,0xed,0x52,0xfe};                         /* 예, 아니오 */
    static const unsigned char *const own[4]={dont_load,dont_save,yes,no};
    for(unsigned i=0;i<4;i++) {
        uint32_t *v=(uint32_t *)(dd+rb->own_slot[i]);
        if(*v==(uint32_t)(uintptr_t)(dd+rb->own_japanese[i])) { *v=(uint32_t)(uintptr_t)own[i]; n++; }
    }
    return n;
}
static int apply_exe_text(uint32_t exe_size) {
    DWORD size=0; unsigned char *blob=read_blob("korean_exe.bin",&size);
    if(!blob) { log_line("exe text skipped: cannot read korean_exe.bin"); return 0; }
    int ok=0;
    if(size<20 || memcmp(blob,"KRX2",4)) { log_line("exe text skipped: bad header"); goto done; }
    uint32_t alloc_size=u32(blob+4),sites=u32(blob+8),writes=u32(blob+12),dd_sites=u32(blob+16);
    if(!alloc_size || alloc_size>0x100000 || sites>4096 || writes>4096 || dd_sites>4096 || !span(size,20,alloc_size) ||
       !span(size,20+alloc_size,sites*12) || size<dd_sites*12) { log_line("exe text skipped: bad bounds"); goto done; }
    /* REbirth rewrites table operands and indexes the tables itself, so its sites are mandatory. */
    uint32_t dd_size=0;
    if(!lookup_ddraw_module || !module_image_size32(lookup_ddraw_module,&dd_size)) { log_line("exe text skipped: verified DDraw unavailable"); goto done; }
    const unsigned char *site=blob+20+alloc_size, *w=site+sites*12, *end=blob+size-dd_sites*12, *dd=end;
    for(uint32_t i=0;i<dd_sites;i++) {
        uintptr_t va=(uintptr_t)lookup_ddraw_module+u32(dd+i*12); uint32_t now;
        if(!image_span((uintptr_t)lookup_ddraw_module,dd_size,va,4) || u32(dd+i*12+8)>alloc_size-4 ||
           ((now=u32((void *)va))!=u32(dd+i*12+4) && now)) {
            log_line("exe text skipped: DDraw guard failed at RVA %08X",u32(dd+i*12)); goto done;
        }
    }
    /* Validate everything before the first write. */
    for(uint32_t i=0;i<sites;i++) {
        const unsigned char *s=site+i*12; uintptr_t va=u32(s);
        int item=va==item_operand_sites[0] || va==item_operand_sites[1];
        if(!image_span(0x400000,exe_size,va,4) || u32(s+8)>alloc_size-4 || (!item && u32((void *)va)!=u32(s+4))) {
            log_line("exe text skipped: operand guard failed at %08lx",(unsigned long)va); goto done;
        }
    }
    for(uint32_t i=0;i<writes;i++) {
        if(end-w<8) { log_line("exe text skipped: truncated write"); goto done; }
        uintptr_t va=u32(w); uint32_t n=u32(w+4);
        if(!n || n>0x10000 || (size_t)(end-w-8)<2u*n || !image_span(0x400000,exe_size,va,n) ||
           (memcmp((void *)va,w+8,n) && memcmp((void *)va,w+8+n,n))) {
            log_line("exe text skipped: data guard failed at %08lx",(unsigned long)va); goto done;
        }
        w+=8+2u*n;
    }
    if(w!=end) { log_line("exe text skipped: trailing bytes"); goto done; }
    exe_text_alloc=VirtualAlloc(NULL,alloc_size,MEM_COMMIT|MEM_RESERVE,PAGE_READWRITE);
    if(!exe_text_alloc) { log_line("exe text skipped: allocation failed"); goto done; }
    memcpy(exe_text_alloc,blob+20,alloc_size);  /* KRX2 header is 20 bytes */
    for(uint32_t i=0;i<sites;i++) {
        const unsigned char *s=site+i*12; uintptr_t va=u32(s);
        uint32_t value=(uint32_t)(uintptr_t)(exe_text_alloc+u32(s+8));
        for(unsigned k=0;k<2;k++) if(va==item_operand_sites[k]) item_operand_values[k]=value;
        patch((void *)va,&value,4);
    }
    for(w=site+sites*12;w<end;w+=8+2u*u32(w+4)) patch((void *)(uintptr_t)u32(w),w+8+u32(w+4),u32(w+4));
    unsigned dd_patched=0;
    for(uint32_t i=0;i<dd_sites;i++) {
        void *va=(unsigned char *)lookup_ddraw_module+u32(dd+i*12);
        uint32_t value=(uint32_t)(uintptr_t)(exe_text_alloc+u32(dd+i*12+8));
        if(u32(va)==u32(dd+i*12+4)) { patch(va,&value,4); dd_patched++; }  /* zero globals: initializer writes Korean later */
    }
    unsigned rebuilt=rebuild_rb_menu_pointers((unsigned char *)lookup_ddraw_module,dd_size);
    log_line("REbirth load-menu pointers rebuilt: %u",rebuilt);
    log_line("exe text applied: %lu operand sites, %lu data writes, %u/%lu DDraw sites, allocation=%p",(unsigned long)sites,(unsigned long)writes,dd_patched,(unsigned long)dd_sites,exe_text_alloc);
    ok=1;
done:
    HeapFree(GetProcessHeap(),0,blob);
    return ok;
}
/* JapaneseEnable=1 keys a document by its whole 256-row VRAM page, and the 80 rows under the
   256x176 document hold leftovers that change with game state. Clearing them first makes
   the page key depend on the document alone. */
static void clear_below_document(const Rect *rect) {
    static const uint16_t zeros[256*80];
    if(rect->h!=176 || (rect->y&255) || rect->w<=0 || rect->w>256) return;
    Rect below={rect->x,(short)(rect->y+176),rect->w,80};
    original_upload(&below,zeros);
    static int logged;
    if(!logged++) log_line("document page lower rows cleared at %d,%d w=%d",rect->x,rect->y,rect->w);
}
static int __cdecl upload_hook(const Rect *rect,const void *source) {
    reapply_item_operands();
    if(rect && source) clear_below_document(rect);
    if(rect && source && font_rect_matches(rect->x,rect->y,rect->w,rect->h)) {
        if(patch_font_atlas(atlas,sizeof atlas,source,256*256*2,font_runs,(size_t)font_count*12,font_count,files,files_size)) {
            return original_upload(rect,atlas);
        }
        log_line("font upload skipped: invalid atlas bounds or run data");
    }
    return original_upload(rect,source);
}
static const RebirthProfile *find_rebirth_profile(HMODULE module) {
    char path[MAX_PATH]; DWORD n=GetModuleFileNameA(module,path,sizeof path);
    if(!n || n>=sizeof path) return NULL;
    HANDLE file=CreateFileA(path,GENERIC_READ,FILE_SHARE_READ|FILE_SHARE_DELETE,NULL,OPEN_EXISTING,FILE_ATTRIBUTE_NORMAL,NULL);
    if(file==INVALID_HANDLE_VALUE) return NULL;
    LARGE_INTEGER file_size; const RebirthProfile *found=NULL;
    for(unsigned i=0;GetFileSizeEx(file,&file_size) && i<sizeof rebirth_profiles/sizeof rebirth_profiles[0];i++)
        if(file_size.QuadPart==rebirth_profiles[i].file_size) found=&rebirth_profiles[i];
    if(!found) { log_line("ddraw.dll size=%lld matches no known REbirth build",(long long)file_size.QuadPart); CloseHandle(file); return NULL; }
    HCRYPTPROV provider=0; HCRYPTHASH hash=0; int ok=CryptAcquireContextA(&provider,NULL,NULL,PROV_RSA_AES,CRYPT_VERIFYCONTEXT) &&
        CryptCreateHash(provider,CALG_SHA_256,0,0,&hash);
    unsigned char block[32768]; DWORD got=0;
    while(ok) {
        if(!ReadFile(file,block,sizeof block,&got,NULL)) { if(GetLastError()==ERROR_HANDLE_EOF) break; ok=0; break; }
        if(!got) break;
        ok=CryptHashData(hash,block,got,0);
    }
    DWORD digest_size=32; unsigned char digest[32];
    ok=ok && CryptGetHashParam(hash,HP_HASHVAL,digest,&digest_size,0) && digest_size==sizeof digest;
    if(hash) CryptDestroyHash(hash); if(provider) CryptReleaseContext(provider,0); CloseHandle(file);
    for(unsigned i=0;ok && i<sizeof rebirth_profiles/sizeof rebirth_profiles[0];i++)
        if(!memcmp(digest,rebirth_profiles[i].sha256,32)) return &rebirth_profiles[i];
    return NULL;
}
__attribute__((used)) static void __cdecl room_loaded(unsigned char *rdt,unsigned size) {
    if(size<0x60 || size>4*1024*1024) { log_line("room callback rejected size=%u",size); return; }
    uintptr_t base=(uintptr_t)rdt, ptr=u32(rdt+0x3c);
    if(ptr<base+0x60 || ptr>=base+size) return;  /* room without a message table */
    uint32_t index=0;
    unsigned stage=*(volatile uint16_t *)0xa673d6+1;
    const unsigned char *translated=match_room(rooms,(const unsigned char *)ptr,base+size-ptr,stage,&index);
    if(translated) {
        uint32_t address=(uintptr_t)translated;
        memcpy(rdt+0x3c,&address,4);
    } else log_line("room unmatched stage=%u size=%u",stage,size);
}
__attribute__((naked)) static void room_hook(void) {
    __asm__ volatile("pushal\n\tpushfl\n\tpush %ebp\n\tpush %esi\n\tcall _room_loaded\n\tadd $8,%esp\n\tpopfl\n\tpopal\n\tmov 1(%esi),%al\n\txor %edx,%edx\n\tret");
}
static int patch(void *dst,const void *src,size_t n) {
    DWORD old,ignored;
    if(!VirtualProtect(dst,n,PAGE_EXECUTE_READWRITE,&old)) return KOREAN_PATCH_FAILED;
    memcpy(dst,src,n); FlushInstructionCache(GetCurrentProcess(),dst,n);
    if(!VirtualProtect(dst,n,old,&ignored)) {
        log_line("WARNING: patch applied but protection restore failed at %p bytes=%lu error=%lu",dst,(unsigned long)n,(unsigned long)GetLastError());
        return KOREAN_PATCH_APPLIED_RESTORE_FAILED;
    }
    return KOREAN_PATCH_APPLIED;
}
static int branch(void *site,void *target,unsigned char opcode) {
    unsigned char b[5]; rel32_branch(b,opcode,(uintptr_t)site,(uintptr_t)target);
    return korean_patch_succeeded(patch(site,b,5));
}
static int branch8(void *site,void *target,unsigned char opcode) {
    unsigned char b[8]; rel32_branch(b,opcode,(uintptr_t)site,(uintptr_t)target);
    memset(b+5,0x90,3); return korean_patch_succeeded(patch(site,b,sizeof b));
}
static int branch9(void *site,void *target,unsigned char opcode) {
    unsigned char b[9]; rel32_branch(b,opcode,(uintptr_t)site,(uintptr_t)target);
    memset(b+5,0x90,4); return korean_patch_succeeded(patch(site,b,sizeof b));
}
static int module_image_size32(HMODULE module,uint32_t *size) {
    if(!module || !size) return 0;
    IMAGE_DOS_HEADER *dos=(IMAGE_DOS_HEADER *)module;
    if(dos->e_magic!=IMAGE_DOS_SIGNATURE || dos->e_lfanew<0 || dos->e_lfanew>0x100000) return 0;
    IMAGE_NT_HEADERS32 *nt=(IMAGE_NT_HEADERS32 *)((unsigned char *)module+dos->e_lfanew);
    if(nt->Signature!=IMAGE_NT_SIGNATURE || nt->OptionalHeader.Magic!=IMAGE_NT_OPTIONAL_HDR32_MAGIC) return 0;
    *size=nt->OptionalHeader.SizeOfImage;
    return 1;
}
__declspec(dllexport) void Modsdk_post_init(void) {
    if(active) return;
    const unsigned char room_expected[]={0x8a,0x46,0x01,0x33,0xd2};
    const unsigned char upload_expected[]={0x8b,0x54,0x24,0x08,0x8b,0x0d,0x14,0x9c,0x53,0x00};
    const unsigned char rebirth_upload_expected[]={0x55,0x8b,0xec,0x83,0xec,0x0c,0x56,0x8b,0x75,0x08,0x0f,0xb7,0x46,0x04,0x0f,0xbf,0xd0};
    HMODULE exe=GetModuleHandleA(NULL);
    log_line("post-init exe=%s base=%p",exe_path,exe);
    if((uintptr_t)exe!=0x400000) { log_line("REFUSED: unexpected executable base %p",exe); return; }
    uint32_t exe_size;
    if(!module_image_size32(exe,&exe_size) ||
       !image_span((uintptr_t)exe,exe_size,0x46ba0e,sizeof room_expected) ||
       !image_span((uintptr_t)exe,exe_size,0x425450,sizeof upload_expected)) {
        log_line("REFUSED: hook sites outside executable image"); return;
    }
    unsigned char *room_site=(unsigned char *)0x46ba0e;
    unsigned char *upload_site=(unsigned char *)0x425450;
    if(!signature_matches(room_site,room_expected,sizeof room_expected)) {
        log_line("REFUSED: room signature mismatch"); return;
    }
    HMODULE ddraw=GetModuleHandleA("ddraw.dll"); uint32_t ddraw_size=0;
    if(!module_image_size32(ddraw,&ddraw_size)) { log_line("REFUSED: ddraw.dll (Classic REbirth) not loaded"); return; }
    rb=find_rebirth_profile(ddraw);
    if(!rb) { log_line("REFUSED: unsupported Classic REbirth ddraw.dll (see README for supported versions)"); return; }
    lookup_ddraw_module=ddraw;
    log_line("Classic REbirth %s",rb->name);
    unsigned char upload_before[5]; memcpy(upload_before,upload_site,sizeof upload_before);
    Upload original=NULL;
    if(signature_matches(upload_site,upload_expected,sizeof upload_expected)) {
        void *trampoline=VirtualAlloc(NULL,32,MEM_COMMIT|MEM_RESERVE,PAGE_EXECUTE_READWRITE);
        if(!trampoline) { log_line("REFUSED: allocation failed"); return; }
        memcpy(trampoline,upload_expected,sizeof upload_expected);
        if(!branch((unsigned char *)trampoline+sizeof upload_expected,upload_site+sizeof upload_expected,0xe9)) {
            log_line("REFUSED: SourceNext trampoline failed"); return;
        }
        original=(Upload)trampoline;
    } else {
        uintptr_t target=0;
        if(upload_site[0]!=0xe9 || !rel32_target(upload_site,(uintptr_t)upload_site,&target) || target!=(uintptr_t)ddraw+rb->upload ||
           !image_span((uintptr_t)ddraw,ddraw_size,target,sizeof rebirth_upload_expected) ||
           !signature_matches((const unsigned char *)target,rebirth_upload_expected,sizeof rebirth_upload_expected)) {
            log_line("REFUSED: REbirth upload target mismatch target=%p ddraw=%p",(void *)target,ddraw); return;
        }
        original=(Upload)target;
    }
    rooms=read_blob("korean_rooms.bin",&rooms_size); files=read_blob("korean_files.bin",&files_size);
    if(!rooms) { log_line("REFUSED: cannot read korean_rooms.bin"); return; }
    if(!validate_rooms(rooms,rooms_size)) { log_line("REFUSED: invalid korean_rooms.bin"); return; }
    if(!files) { log_line("REFUSED: cannot read korean_files.bin"); return; }
    if(!load_fonts()) { log_line("REFUSED: invalid korean_files.bin or font runs"); return; }
    original_upload=original;
    if(!branch(upload_site,upload_hook,0xe9)) { log_line("REFUSED: upload hook failed"); return; }
    if(!branch(room_site,room_hook,0xe8)) {
        patch(upload_site,upload_before,sizeof upload_before);
        log_line("REFUSED: room hook failed"); return;
    }
    apply_exe_text(exe_size);
    load_rebirth_text();
    active=1;
    log_line("initialized RE3 Korean HD: %u room tables, %u font runs",u32(rooms+4),font_count);
}
__declspec(dllexport) void Modsdk_load(unsigned char *src,size_t pos,size_t size) { (void)src;(void)pos;(void)size; }
__declspec(dllexport) void Modsdk_save(unsigned char **dst,size_t *size) { *dst=NULL; *size=0; }
BOOL WINAPI DllMain(HINSTANCE h,DWORD reason,LPVOID reserved) {
    (void)reserved;
    if(reason==DLL_PROCESS_ATTACH) {
        (void)h;
        /* REbirth manually maps this DLL, so its handle is not a Win32 module. */
        DWORD n=GetModuleFileNameA(NULL,exe_path,sizeof exe_path);
        if(!n || n>=sizeof exe_path) return FALSE;
        memcpy(folder,exe_path,n+1);
        char *slash=strrchr(folder,'\\'); if(!slash) return FALSE; slash[1]=0;
        if(strlen(folder)+sizeof "mod_korean_hd\\">sizeof folder) return FALSE;
        strcat(folder,"mod_korean_hd\\");
        char path[MAX_PATH]; snprintf(path,sizeof path,"%skorean_hd.log",folder);
        DeleteFileA(path);  /* one log per launch */
        log_line("RE3 Korean HD %s",KOREAN_HD_VERSION);
        log_line("attach exe=%s base=%p",exe_path,GetModuleHandleA(NULL));
    }
    return TRUE;
}
