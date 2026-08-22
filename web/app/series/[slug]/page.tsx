import { ContentDetailExperience } from '@/features/detail/ContentDetailExperience';
export default async function Page({params}:{params:Promise<{slug:string}>}){const {slug}=await params;return <ContentDetailExperience type="series" slug={slug}/>}
