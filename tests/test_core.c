#include <assert.h>
#include <stdlib.h>
#include <stdio.h>
#include "../src/korean_core.h"
#if defined(__i386__) || defined(_M_IX86)
#define TEST_FASTCALL __attribute__((fastcall))
__attribute__((noinline)) static uintptr_t stack_pointer(void) { uintptr_t p; __asm__ volatile("mov %%esp,%0":"=r"(p)); return p; }
#else
#define TEST_FASTCALL
#endif
typedef struct { uint32_t pixels,width,height,ownership; } MockTextureInfo;
_Static_assert(sizeof(MockTextureInfo)==16 && offsetof(MockTextureInfo,pixels)==0 &&
    offsetof(MockTextureInfo,width)==4 && offsetof(MockTextureInfo,height)==8 &&
    offsetof(MockTextureInfo,ownership)==12,"native DDraw output layout");
__attribute__((noinline)) static unsigned char TEST_FASTCALL mock_lookup(uint32_t key,void *out) {
    MockTextureInfo *info=(MockTextureInfo *)out;
    if(key!=0x8320a534 || !info) return 0;
    info->pixels=0x12345678; info->width=256; info->height=72; info->ownership=1;
    return 1;
}
static unsigned char *read_asset(const char *root,const char *relative,size_t *size) {
    char path[1024]; int n=snprintf(path,sizeof path,"%s/%s",root,relative);
    assert(n>0 && (size_t)n<sizeof path);
    for(char *p=path;*p;p++) if(*p=='\\') *p='/';
    FILE *f=fopen(path,"rb"); assert(f && !fseek(f,0,SEEK_END));
    long length=ftell(f); assert(length>0 && length<=16*1024*1024 && !fseek(f,0,SEEK_SET));
    unsigned char *data=malloc((size_t)length); assert(data && fread(data,1,(size_t)length,f)==(size_t)length);
    fclose(f); *size=(size_t)length; return data;
}
int main(int argc,char **argv) {
    static const char *source_paths[]={
        "Data_aj/Etc2/CHECKJ.TIM","Data_aj/Etc2/FILEGJ03.TIM","Data_aj/Etc2/FILEGJ04.TIM",
        "Data_aj/Etc2/FILEGJ05.TIM","Data_aj/Etc2/FILEGJ06.TIM","Data/Etc/STR_BG.DAT",
        "Data_j/Etc2/END0.CPT","Data_j/Etc2/END1.CPT","Data_j/Etc2/FILEGJ.PIX",
        "Data_j/Etc2/FONTST0J.TIM","Data_j/Etc2/FONTST1J.TIM","Data_j/Etc2/FONTST2J.TIM",
        "Data_j/Etc2/FONTST3J.TIM","Data_j/Etc2/FONTST4J.TIM","Data_j/Etc2/FONTST5J.TIM",
        "Data_j/Etc2/FONTST6J.TIM","Data_j/Etc2/FONTST7J.TIM","Data_j/Etc2/INS06.CPT",
        "Data_j/Etc2/OMBG_J.DAT","Data_j/Etc2/OPTIONJ.DAT","Data_j/Etc2/STMOJIJ.TIM",
        "Data_j/Etc2/TEXJ.TIM","Data_j/Etc2/WARNJ.TIM"
    };
    assert(sizeof source_paths/sizeof source_paths[0]==23);
    for(size_t i=0;i<sizeof source_paths/sizeof source_paths[0];i++) {
        char full[96]; snprintf(full,sizeof full,"Bio19/%s",source_paths[i]);
        const KoreanFileOverride *file=korean_file_override(full);
        assert(file && path_equal(file->source,source_paths[i]));
    }
    assert(korean_file_override(NULL)==NULL);
    assert(!strcmp(korean_file_override("Bio19/Data_j/Etc2/FONTST1J.TIM")->override,"DATA_J\\ETC2\\FONTST1J.TIM"));
    assert(!strcmp(korean_file_override("C:\\game\\Bio19\\Data_aj\\Etc2\\CHECKJ.TIM")->override,"DATA_AJ\\ETC2\\CHECKJ.TIM"));
    assert(!strcmp(korean_file_override("bio19/data/etc/str_bg.dat")->override,"DATA\\ETC\\STR_BG.DAT"));
    assert(korean_file_override("Bio19/Data_j/Etc2/../FONTST1J.TIM")==NULL);
    assert(korean_file_override("Bio19/Data_j/Etc2/FONTST1J.TIM.bak")==NULL);
    assert(korean_file_override("Bio19ish/Data_j/Etc2/FONTST1J.TIM")==NULL);
    assert(korean_file_override("Bio19/Data_j/RDT/R101.RDT")==NULL);
    const unsigned char sig[]={0x8a,0x46,0x01,0x33,0xd2}, altered[]={0x8a,0x46,0x02,0x33,0xd2};
    assert(signature_matches(sig,sig,sizeof sig));
    assert(!signature_matches(sig,altered,sizeof sig) && !signature_matches(NULL,sig,sizeof sig));
    assert(font_rect_matches(768,256,256,256));
    assert(!font_rect_matches(448,256,256,256) && !font_rect_matches(768,255,256,256) && !font_rect_matches(768,256,128,256));
    unsigned char *src=malloc(131072), *guarded=malloc(131072+2), run[12]={0}, glyph[2]={0xaa,0xbb};
    assert(src && guarded);
    memset(src,0x5a,131072); memset(guarded,0xa5,131074);
    uint16_t x=894,y=511,w=1; uint32_t glyph_off=0;
    memcpy(run,&x,2); memcpy(run+2,&y,2); memcpy(run+4,&w,2); memcpy(run+8,&glyph_off,4);
    assert(patch_font_atlas(guarded+1,131072,src,131072,run,sizeof run,1,glyph,sizeof glyph));
    assert(guarded[0]==0xa5 && guarded[131073]==0xa5);
    assert(guarded[1]==0x5a && guarded[131072]==0x5a);
    assert(!memcmp(guarded+1+255*512+126*2,glyph,2));
    memset(guarded,0xa5,131074);
    assert(!patch_font_atlas(guarded+1,131071,src,131072,run,sizeof run,1,glyph,sizeof glyph));
    assert(guarded[0]==0xa5 && guarded[1]==0xa5 && guarded[131073]==0xa5);
    free(guarded); free(src);
    assert(image_span(0x400000,0x10000,0x400000,1));
    assert(image_span(0x400000,0x10000,0x410000,0));
    assert(!image_span(0x400000,0x10000,0x40ffff,2));
    assert(!image_span(0x400000,0x10000,0x3fffff,1));
    assert(!image_span(0x400000,0x10000,UINTPTR_MAX,1));
    assert(font_source_span(0x400000,131072,0x400000,131072));
    assert(!font_source_span(0x400000,131072,0x400000,131071));
    assert(!font_source_span(0x400000,131071,0x400000,131072));
    assert(!font_source_span(0x400000,131072,0x400001,131072));
    assert(!font_source_span(0x400000,131072,UINTPTR_MAX,131072));
    assert(!korean_patch_succeeded(KOREAN_PATCH_FAILED));
    assert(korean_patch_succeeded(KOREAN_PATCH_APPLIED));
    assert(korean_patch_succeeded(KOREAN_PATCH_APPLIED_RESTORE_FAILED));
    assert(readable_protection(0x02) && readable_protection(0x04) && readable_protection(0x08));
    assert(readable_protection(0x20) && readable_protection(0x40) && readable_protection(0x80));
    assert(!readable_protection(0x01) && !readable_protection(0x10));
    assert(!readable_protection(0x102) && !readable_protection(0x120));
    unsigned char branch_bytes[5]; rel32_branch(branch_bytes,0xe8,0x00401000,0x00402000);
    const unsigned char forward[]={0xe8,0xfb,0x0f,0x00,0x00};
    assert(!memcmp(branch_bytes,forward,sizeof forward));
    rel32_branch(branch_bytes,0xe9,0x00402000,0x00401000);
    const unsigned char backward[]={0xe9,0xfb,0xef,0xff,0xff};
    assert(!memcmp(branch_bytes,backward,sizeof backward));
    uintptr_t target=0;
    assert(rel32_target(forward,0x00401000,&target) && target==0x00402000);
    assert(rel32_target(backward,0x00402000,&target) && target==0x00401000);
    const unsigned char direct_file[]={0x53,0x55,0x56,0x8b,0x74,0x24,0x10,0x57};
    const unsigned char ddraw_file[]={0x53,0x8b,0xdc,0x83,0xec,0x08,0x83,0xe4,0xf8,0x83,0xc4,0x04};
    const unsigned char load_file_entry[]={0xe9,0xeb,0x19,0x61,0x7a,0x24,0x10,0x57};
    const uintptr_t exe_base=0x00400000, file_site=0x00428810, ddraw_base=0x7a9c0000;
    const uint32_t exe_size=0x00b01000, ddraw_size=0x0096a000, ddraw_rva=0x0007a200;
    unsigned char file_entry[8]; memcpy(file_entry,direct_file,sizeof file_entry);
    assert(korean_file_loader_route(file_entry,file_site,exe_base,exe_size,direct_file,sizeof direct_file,
        ddraw_base,ddraw_size,ddraw_rva,ddraw_file,ddraw_file,sizeof ddraw_file,&target)==KOREAN_FILE_ROUTE_DIRECT);
    assert(target==file_site);
    memcpy(file_entry,load_file_entry,sizeof file_entry);
    assert(korean_file_loader_route(file_entry,file_site,exe_base,exe_size,direct_file,sizeof direct_file,
        ddraw_base,ddraw_size,ddraw_rva,ddraw_file,ddraw_file,sizeof ddraw_file,&target)==KOREAN_FILE_ROUTE_DDRAW);
    assert(target==ddraw_base+ddraw_rva);
    assert(korean_file_loader_route(file_entry,file_site,exe_base,0x28815,direct_file,sizeof direct_file,
        ddraw_base,ddraw_size,ddraw_rva,ddraw_file,ddraw_file,sizeof ddraw_file,&target)==KOREAN_FILE_ROUTE_DDRAW);
    assert(korean_file_loader_route(file_entry,file_site,exe_base,0x28814,direct_file,sizeof direct_file,
        ddraw_base,ddraw_size,ddraw_rva,ddraw_file,ddraw_file,sizeof ddraw_file,&target)==KOREAN_FILE_ROUTE_NONE);
    const unsigned char wrong_ddraw[]={0x55,0x89,0xe5,0x53,0x57,0x56,0x83,0xec,0x14,0x8b,0x75,0x08};
    assert(korean_file_loader_route(file_entry,file_site,exe_base,exe_size,direct_file,sizeof direct_file,
        ddraw_base,ddraw_size,ddraw_rva,wrong_ddraw,ddraw_file,sizeof ddraw_file,&target)==KOREAN_FILE_ROUTE_NONE);
    assert(korean_file_loader_route(file_entry,file_site,exe_base,exe_size,direct_file,sizeof direct_file,
        ddraw_base+0x1000,ddraw_size,ddraw_rva,ddraw_file,ddraw_file,sizeof ddraw_file,&target)==KOREAN_FILE_ROUTE_NONE);
    rel32_branch(file_entry,0xe9,(uint32_t)file_site,(uint32_t)(ddraw_base+ddraw_rva+4));
    uintptr_t untouched=0x12345678;
    assert(korean_file_loader_route(file_entry,file_site,exe_base,exe_size,direct_file,sizeof direct_file,
        ddraw_base,ddraw_size,ddraw_rva,ddraw_file,ddraw_file,sizeof ddraw_file,&untouched)==KOREAN_FILE_ROUTE_NONE);
    assert(untouched==0x12345678);
    const unsigned char invalid_branch[]={0x90,0,0,0,0};
    assert(!rel32_target(invalid_branch,0x00401000,&target) && !rel32_target(NULL,0x00401000,&target));
    assert(crc32_bytes((const unsigned char *)"123456789",9)==0xcbf43926);
    uint32_t diag_keys[KOREAN_HD_DIAG_CAPACITY]={0}; unsigned char diag_states[KOREAN_HD_DIAG_CAPACITY]={0}; unsigned diag_slot=0;
    for(unsigned i=0;i<KOREAN_HD_DIAG_CAPACITY-KOREAN_HD_DIAG_RESERVED;i++)
        assert(korean_hd_diag_record(diag_keys,diag_states,0x90000000u+i,0,&diag_slot));
    assert(!korean_hd_diag_record(diag_keys,diag_states,0x90000001u,0,&diag_slot));
    assert(korean_hd_diag_record(diag_keys,diag_states,0x8320a534,0,&diag_slot) && diag_slot==1);
    assert(korean_hd_diag_record(diag_keys,diag_states,0x8320a534,1,&diag_slot) && diag_slot==1);
    assert(!korean_hd_diag_record(diag_keys,diag_states,0x8320a534,1,&diag_slot));
    uint32_t bounded_keys[KOREAN_HD_DIAG_CAPACITY]={0};
    unsigned char bounded_states[KOREAN_HD_DIAG_CAPACITY]={0}; unsigned bounded_events=0;
    for(unsigned i=0;i<KOREAN_HD_DIAG_CAPACITY;i++) {
        uint32_t key=i<KOREAN_HD_DIAG_RESERVED?korean_hd_diagnostic_keys[i]:0x91000000u+i;
        assert(korean_hd_diag_record(bounded_keys,bounded_states,key,0,&diag_slot)); bounded_events++;
        assert(korean_hd_diag_record(bounded_keys,bounded_states,key,1,&diag_slot)); bounded_events++;
        assert(!korean_hd_diag_record(bounded_keys,bounded_states,key,1,&diag_slot));
    }
    assert(bounded_events==2*KOREAN_HD_DIAG_CAPACITY);
    assert(!korean_hd_diag_record(bounded_keys,bounded_states,0x92000000u,0,&diag_slot));
    unsigned char key_map[16]={0}, asset_records[48]={0}; char resolved[64];
    uint32_t low_key=0x8320a534, high_key=0xcc541949; uint16_t record_index=1;
    memcpy(key_map,&low_key,4); memcpy(key_map+4,&record_index,2); memcpy(key_map+8,&high_key,4);
    memcpy(asset_records+24,"misc",5);
    assert(korean_hd_lookup_path(low_key,key_map,sizeof key_map,asset_records,sizeof asset_records,resolved,sizeof resolved));
    assert(!strcmp(resolved,"hires\\misc\\8320A534.webp"));
    assert(!korean_hd_lookup_path(low_key,key_map,7,asset_records,sizeof asset_records,resolved,sizeof resolved));
    assert(!korean_hd_lookup_path(low_key,key_map,sizeof key_map,asset_records,24,resolved,sizeof resolved));
    assert(!korean_hd_lookup_path(0x77777777,key_map,sizeof key_map,asset_records,sizeof asset_records,resolved,sizeof resolved));
    MockTextureInfo mock_info={0};
#if defined(__i386__) || defined(_M_IX86)
    uintptr_t before_sp=stack_pointer();
#endif
    assert(mock_lookup(0x8320a534,&mock_info)==1);
#if defined(__i386__) || defined(_M_IX86)
    assert(stack_pointer()==before_sp);
#endif
    assert(mock_info.pixels==0x12345678 && mock_info.width==256 && mock_info.height==72 && mock_info.ownership==1);
    assert(mock_lookup(0x12345678,&mock_info)==0);
    assert(span(10,10,0) && !span(10,11,0) && !span(10,9,2));
    assert(argc==4);
    for(size_t i=0;i<sizeof source_paths/sizeof source_paths[0];i++) {
        char full[96]; snprintf(full,sizeof full,"Bio19/%s",source_paths[i]);
        const KoreanFileOverride *file=korean_file_override(full);
        size_t original_size,patched_size;
        unsigned char *original=read_asset(argv[2],file->override,&original_size);
        unsigned char *patched=read_asset(argv[3],file->override,&patched_size);
        assert(korean_file_source_matches(file,original,original_size));
        assert(!korean_file_replacement_matches(file,original,original_size));
        assert(korean_file_replacement_matches(file,patched,patched_size));
        assert(!korean_file_source_matches(file,patched,patched_size));
        assert(!korean_file_source_matches(file,original,original_size-1));
        assert(!korean_file_replacement_matches(file,patched,patched_size-1));
        original[0]^=1; patched[0]^=1;
        assert(!korean_file_source_matches(file,original,original_size));
        assert(!korean_file_replacement_matches(file,patched,patched_size));
        original[0]^=1; patched[0]^=1;
        assert(korean_file_source_matches(file,original,original_size));
        assert(korean_file_replacement_matches(file,patched,patched_size));
        free(original); free(patched);
    }
    assert(!korean_file_source_matches(korean_file_override("Bio19/Data_j/Etc2/FONTST1J.TIM"),NULL,33440));
    static const unsigned char status_rects[9][4]={
        {0,40,32,16},{72,40,32,16},{32,40,40,16},
        {0,32,24,8},{24,32,40,8},{64,32,40,8},{104,32,40,8},{144,32,32,8},{184,32,32,8}
    };
    for(unsigned i=0;i<9;i++) {
        for(unsigned opcode=0x64;opcode<=0x67;opcode++) {
            unsigned char packet[20]={0}; packet[7]=(unsigned char)opcode; packet[0x0c]=status_rects[i][0]; packet[0x0d]=status_rects[i][1];
            packet[0x10]=status_rects[i][2]; packet[0x12]=status_rects[i][3];
            assert(korean_status_packet_index(packet,sizeof packet)==(int)i);
            assert(korean_status_packet_index(packet,sizeof packet-1)==-1);
        }
    }
    unsigned char status_packet[20]={0}; status_packet[7]=0x64;
    status_packet[0x0d]=40; status_packet[0x10]=32; status_packet[0x12]=16;
    assert(korean_status_packet_index(status_packet,sizeof status_packet)==0);
    status_packet[7]=0x63; assert(korean_status_packet_index(status_packet,sizeof status_packet)==-1);
    status_packet[7]=0x68; assert(korean_status_packet_index(status_packet,sizeof status_packet)==-1);
    status_packet[7]=0x64; status_packet[0x0c]=1; assert(korean_status_packet_index(status_packet,sizeof status_packet)==-1);
    assert(korean_status_packet_index(NULL,20)==-1);
    unsigned char font_packet[20]={0}; font_packet[7]=0x64; font_packet[0x0e]=0x13; font_packet[0x0f]=0x78;
    font_packet[0x10]=14; font_packet[0x12]=14;
    assert(korean_font_sprite_packet(font_packet,sizeof font_packet));
    font_packet[0x0f]=0x77; assert(!korean_font_sprite_packet(font_packet,sizeof font_packet));
    font_packet[0x0f]=0x78; font_packet[0x12]=13; assert(!korean_font_sprite_packet(font_packet,sizeof font_packet));
    uint16_t dedupe[2][9]={{0}}, key[9]={0};
    assert(diagnostic_seen(dedupe,0,2,key)==1);
    assert(diagnostic_seen(dedupe,1,2,key)==0);
    key[8]=0x1a; assert(diagnostic_seen(dedupe,1,2,key)==1);
    assert(diagnostic_seen(dedupe,2,2,key)==-1);
    FILE *f=fopen(argv[1],"rb"); assert(f); fseek(f,0,SEEK_END); long n=ftell(f); rewind(f);
    unsigned char *b=malloc(n); assert(b && fread(b,1,n,f)==(size_t)n); fclose(f);
    assert(validate_rooms(b,n));
    unsigned char synthetic[44]={0}; memcpy(synthetic,"KRM3",4);
    uint32_t one=1,three=3,off=40,crc=crc32_bytes((unsigned char *)"abc",3);
    memcpy(synthetic+4,&one,4); memcpy(synthetic+8,&one,4); memcpy(synthetic+12,&crc,4);
    memcpy(synthetic+16,&three,4); memcpy(synthetic+24,&off,4); memcpy(synthetic+28,&three,4); memcpy(synthetic+40,"xyz",3);
    assert(validate_rooms(synthetic,sizeof synthetic)); uint32_t index=99;
    assert(match_room(synthetic,(unsigned char *)"abc",3,1,&index)==synthetic+40 && index==0);
    assert(!match_room(synthetic,(unsigned char *)"abd",3,1,&index));
    assert(!match_room(synthetic,(unsigned char *)"abc",2,1,&index));
    assert(match_room(synthetic,(unsigned char *)"abc",3,2,&index)==synthetic+40 && index==0); /* stage word may lag */
    synthetic[36]=1; assert(!validate_rooms(synthetic,sizeof synthetic));
    synthetic[36]=0; synthetic[24]=250; assert(!validate_rooms(synthetic,sizeof synthetic));
    free(b); puts("core CRC, all 23 ROFS-to-Korean overrides, mismatch guards, room matching and truncation passed");
}
